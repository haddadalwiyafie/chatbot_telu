#!/usr/bin/env python3
"""
Evaluation harness for the Tiva RAG chatbot (Telkom University).

Reproduces the deployed pipeline (whole-page ingestion truncated to 3,000
characters, Cohere embed-v4.0, Chroma L2 search, k = 3, Gemini, Indonesian
"stuff" prompt) and compares it with controlled variants:

  ingestion : naive (as deployed)  vs  clean (binary filter + de-duplication +
              boilerplate removal + recursive chunking with a page-title header)
  retriever : dense (Cohere)  vs  BM25  vs  hybrid (reciprocal rank fusion)
  k         : 1, 3, 5, 10
  generator : RAG configurations vs an LLM-only baseline (no retrieval)

Sub-commands
  check       validate the test set against the corpus (offline, no API keys)
  retrieval   retrieval metrics for every ingestion x retriever x k
  generation  answers + LLM-as-judge scores for the configurations G0..G4
  report      paper-ready markdown tables from the saved results
  human-sample  rebuild the blinded annotation sheet (and its separate key) from generation.jsonl
  kappa       agreement between the human annotator(s) and the LLM judge

Add --mock to any sub-command to run offline with a hashing embedder, an echo
generator and a heuristic judge (smoke test only: those numbers mean nothing).

Usage (from the repository root, with COHERE_API_KEY and GEMINI_API_KEY in .env):
  python eval/evaluate.py check
  python eval/evaluate.py retrieval
  python eval/evaluate.py generation --sleep 6
  python eval/evaluate.py report
"""
import argparse, csv, hashlib, json, math, os, pickle, platform, random, re, statistics, sys, time
from collections import Counter, defaultdict
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
TRUNC = 3000  # characters kept per document by load_to_chroma.py / generate_to_chroma.py

# The deployed prompt, copied verbatim from langchain_pipeline.py
RAG_PROMPT = """
Gunakan informasi berikut untuk menjawab pertanyaan secara ringkas, detail, langsung, dan dalam Bahasa Indonesia.
Jika tidak ditemukan jawabannya, cukup katakan "Informasi tidak ditemukan."

{context}

Pertanyaan: {question}
Jawaban:
"""
# Same instruction without retrieved context (LLM-only baseline, G0)
LLM_ONLY_PROMPT = """
Jawablah pertanyaan berikut tentang Telkom University secara ringkas, detail, langsung, dan dalam Bahasa Indonesia.
Jika tidak ditemukan jawabannya, cukup katakan "Informasi tidak ditemukan."

Pertanyaan: {question}
Jawaban:
"""
REFUSAL = "informasi tidak ditemukan"

GEN_CONFIGS = {
    "G0": dict(label="LLM only (no retrieval)", ingestion=None, retriever=None, k=0),
    "G1": dict(label="Deployed: naive ingestion + dense, k=3", ingestion="naive", retriever="dense", k=3),
    "G2": dict(label="Clean ingestion + dense, k=3", ingestion="clean", retriever="dense", k=3),
    "G3": dict(label="Clean ingestion + hybrid, k=3", ingestion="clean", retriever="hybrid", k=3),
    "G4": dict(label="Clean ingestion + hybrid, k=5", ingestion="clean", retriever="hybrid", k=5),
}

# ----------------------------------------------------------------------------- text utils
def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()

STOP = set("""yang dan di ke dari untuk dengan pada adalah ini itu apa apakah berapa siapa kapan mana
bagaimana mengapa kenapa saja serta atau juga dalam oleh sebagai bisa dapat akan telah sudah ada
tidak saya kamu anda kami kita telkom university universitas tel-u""".split())
TOKEN_RE = re.compile(r"[0-9]+(?:[.,][0-9]+)*|\w+", re.UNICODE)

def tokens(s, stop=True):
    toks = TOKEN_RE.findall(s.lower())
    return [t for t in toks if not (stop and t in STOP)]

def token_f1(pred, ref):
    p, r = tokens(pred), tokens(ref)
    if not p or not r:
        return float(p == r)
    common = Counter(p) & Counter(r)
    n = sum(common.values())
    if n == 0:
        return 0.0
    prec, rec = n / len(p), n / len(r)
    return 2 * prec * rec / (prec + rec)

def sha1(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

# ----------------------------------------------------------------------------- corpus
def detect_text_columns(headers):
    # copied from generate_to_chroma.py so CSV rows are read exactly as deployed
    keywords = ["judul", "isi", "teks", "keterangan", "konten", "deskripsi", "description", "title"]
    matching = [h for h in headers if any(k in h.lower() for k in keywords)]
    if len(matching) >= 2:
        return matching[:2]
    elif len(matching) == 1:
        return matching[0], ""
    elif len(headers) >= 2:
        return headers[0], headers[1]
    elif len(headers) == 1:
        return headers[0], ""
    return "", ""

def load_raw_corpus(repo):
    """Every source document exactly as the two ingestion scripts read it."""
    docs = []
    with open(os.path.join(repo, "data_telkom.json"), encoding="utf-8") as f:
        for i, d in enumerate(json.load(f)):
            docs.append(dict(id=f"doc-{i}", url=d.get("url", ""), origin="crawl", text=d.get("content", "")))
    folder = os.path.join(repo, "data")
    for fn in sorted(os.listdir(folder)):
        p = os.path.join(folder, fn)
        ext = os.path.splitext(fn)[1].lower()
        if ext == ".csv":
            with open(p, encoding="utf-8") as f:
                sample = f.read(5000)
                delim = ";" if ";" in sample else ","
                f.seek(0)
                rdr = csv.DictReader(f, delimiter=delim)
                c1, c2 = detect_text_columns(rdr.fieldnames)
                url_col = next((h for h in rdr.fieldnames if h.strip().lower() in ("link", "url")), None)
                for i, row in enumerate(rdr):
                    docs.append(dict(id=f"{fn}-{i}", url=row.get(url_col, "") if url_col else fn,
                                     origin="csv", text=f"{row.get(c1, '')}\n{row.get(c2, '')}"))
        elif ext == ".txt":
            with open(p, encoding="utf-8") as f:
                docs.append(dict(id=f"{fn}-0", url=fn, origin="txt", text=f.read()))
    return docs

def naive_units(docs):
    """Mirror of load_to_chroma.py (crawl: content[:3000]) and generate_to_chroma.py (strip()[:3000])."""
    units = []
    for d in docs:
        t = d["text"][:TRUNC] if d["origin"] == "crawl" else d["text"].strip()[:TRUNC]
        if not t.strip():
            continue
        units.append(dict(id=d["id"], parent=d["id"], text=t))
    return units

BIN_EXT = re.compile(r"\.(png|jpe?g|gif|webp|svg|pdf|zip|docx?|xlsx?|pptx?)(\?.*)?$", re.I)

def is_binary(d):
    if BIN_EXT.search(d["url"] or ""):
        return True
    t = d["text"][:2000]
    if not t:
        return False
    bad = sum(1 for ch in t if ch == "�" or (ord(ch) < 32 and ch not in "\n\t\r"))
    return bad / len(t) > 0.05

def host_of(d):
    return urlparse(d["url"]).netloc or "local"

def clean_docs(docs, boiler_frac=0.3, boiler_min=3):
    """Binary filter, exact de-duplication and per-host boilerplate removal.
    Boilerplate lines are not thrown away: each host keeps them once in a 'site::<host>' document,
    so footer facts (addresses, phone numbers) stay retrievable."""
    stats = Counter()
    kept, seen = [], set()
    for d in docs:
        if is_binary(d):
            stats["binary_dropped"] += 1
            continue
        h = sha1(norm(d["text"]))
        if h in seen:
            stats["duplicates_dropped"] += 1
            continue
        if not d["text"].strip():
            stats["empty_dropped"] += 1
            continue
        seen.add(h)
        kept.append(d)
    byhost = defaultdict(list)
    for d in kept:
        byhost[host_of(d)].append(d)
    out = []
    for host, ds in byhost.items():
        cnt = Counter()
        for d in ds:
            cnt.update(set(l.strip() for l in d["text"].split("\n") if l.strip()))
        thr = max(boiler_min, math.ceil(boiler_frac * len(ds)))
        boiler = {l for l, n in cnt.items() if n >= thr}
        site_lines, site_seen = [], set()
        for d in ds:
            body = []
            for l in (x.strip() for x in d["text"].split("\n")):
                if not l:
                    continue
                if l in boiler:
                    if l not in site_seen:
                        site_seen.add(l)
                        site_lines.append(l)
                    stats["boilerplate_lines_removed"] += 1
                    continue
                body.append(l)
            if body:
                out.append(dict(d, text="\n".join(body)))
        if site_lines:
            out.append(dict(id=f"site::{host}", url=f"https://{host}/" if host != "local" else "local",
                            origin="site-boilerplate", text="\n".join(site_lines)))
    stats["docs_after_cleaning"] = len(out)
    return out, stats

def make_splitter(chunk_size, overlap):
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        sp = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        return sp.split_text
    except ImportError:  # fallback: greedy line packing with character overlap
        print("[warn] langchain_text_splitters not installed; using a simple fallback splitter", file=sys.stderr)
        def split(text):
            chunks, cur = [], ""
            for line in text.split("\n"):
                while len(line) > chunk_size:
                    chunks.append(line[:chunk_size]); line = line[chunk_size - overlap:]
                if len(cur) + len(line) + 1 > chunk_size and cur:
                    chunks.append(cur); cur = cur[-overlap:] + "\n" + line
                else:
                    cur = f"{cur}\n{line}" if cur else line
            if cur:
                chunks.append(cur)
            return chunks
        return split

def clean_units(docs, chunk_size=1000, overlap=150, header=True):
    cdocs, stats = clean_docs(docs)
    split = make_splitter(chunk_size, overlap)
    units = []
    for d in cdocs:
        title = d["text"].split("\n", 1)[0][:150]
        for j, ch in enumerate(split(d["text"])):
            text = f"[{title}] ({d['url']})\n{ch}" if header else ch
            units.append(dict(id=f"{d['id']}#c{j}", parent=d["id"], text=text))
    stats["chunks"] = len(units)
    return units, stats

def build_units(docs, ingestion, chunk_size=1000, overlap=150):
    if ingestion == "naive":
        return naive_units(docs)
    return clean_units(docs, chunk_size, overlap)[0]

# ----------------------------------------------------------------------------- test set
def load_testset(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def evidence_in(text_norm, ev):
    return norm(ev) in text_norm

# ----------------------------------------------------------------------------- embeddings
class _SafeUnpickler(pickle.Unpickler):
    """Load only plain containers and numpy arrays from the cache, never arbitrary objects."""
    ALLOWED = {("numpy", "ndarray"), ("numpy", "dtype"), ("numpy.core.multiarray", "_reconstruct"),
               ("numpy._core.multiarray", "_reconstruct"), ("numpy.core.multiarray", "scalar"),
               ("numpy._core.multiarray", "scalar"), ("builtins", "dict")}
    def find_class(self, module, name):
        if (module, name) in self.ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"refusing to load {module}.{name} from the embedding cache")

class EmbCache:
    def __init__(self, path):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            with open(path, "rb") as f:
                self.data = _SafeUnpickler(f).load()
    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "wb") as f:
            pickle.dump(self.data, f)

class CohereEmbedder:
    """Same model and input types as langchain_pipeline.py, batched, with an on-disk cache."""
    def __init__(self, model, cache_dir):
        import cohere
        key = os.getenv("COHERE_API_KEY")
        if not key:
            sys.exit("COHERE_API_KEY is not set (put it in .env)")
        self.client = cohere.Client(api_key=key)
        self.model = model
        self.cache = {t: EmbCache(os.path.join(cache_dir, f"emb_{model}_{t}.pkl")) for t in ("search_document", "search_query")}
    def embed(self, texts, input_type):
        import numpy as np
        cache = self.cache[input_type]
        todo = [t for t in dict.fromkeys(texts) if sha1(t) not in cache.data]
        for i in range(0, len(todo), 96):
            batch = todo[i:i + 96]
            for attempt in range(6):
                try:
                    r = self.client.embed(texts=batch, model=self.model, input_type=input_type)
                    break
                except Exception as e:  # rate limit or transient error
                    wait = 2 ** attempt * 5
                    print(f"[embed] {e.__class__.__name__}: retry in {wait}s", file=sys.stderr)
                    time.sleep(wait)
            else:
                raise RuntimeError("embedding failed after retries")
            embs = r.embeddings if isinstance(r.embeddings, list) else r.embeddings.float_
            for t, e in zip(batch, embs):
                cache.data[sha1(t)] = np.asarray(e, dtype="float32")
            cache.save()
        return np.stack([cache.data[sha1(t)] for t in texts])

class HashEmbedder:
    """--mock only: feature-hashing bag of words (no network)."""
    def __init__(self, dim=512):
        self.dim = dim
    def embed(self, texts, input_type):
        import numpy as np
        M = np.zeros((len(texts), self.dim), dtype="float32")
        for i, t in enumerate(texts):
            for tok in tokens(t):
                M[i, int(sha1(tok)[:8], 16) % self.dim] += 1.0
        n = np.linalg.norm(M, axis=1, keepdims=True); n[n == 0] = 1
        return M / n

# ----------------------------------------------------------------------------- retrievers
class DenseIndex:
    """Exact squared-L2 search (Chroma's default space). --index chroma uses an in-memory Chroma collection instead."""
    def __init__(self, units, embedder, use_chroma=False):
        import numpy as np
        self.units, self.embedder = units, embedder
        self.M = embedder.embed([u["text"] for u in units], "search_document")
        self.chroma = None
        if use_chroma:
            import chromadb
            client = chromadb.EphemeralClient()
            name = "eval_" + sha1(str(time.time()))[:8]
            self.chroma = client.create_collection(name)
            for i in range(0, len(units), 500):
                self.chroma.add(ids=[str(j) for j in range(i, min(i + 500, len(units)))],
                                embeddings=self.M[i:i + 500].tolist(),
                                documents=[u["text"] for u in units[i:i + 500]])
        self.np = np
    def search(self, query, n):
        n = min(n, len(self.units))
        q = self.embedder.embed([query], "search_query")[0]
        if self.chroma is not None:
            r = self.chroma.query(query_embeddings=[q.tolist()], n_results=n)
            return [int(i) for i in r["ids"][0]]
        d = ((self.M - q) ** 2).sum(axis=1)
        return [int(i) for i in self.np.argsort(d, kind="stable")[:n]]

class BM25Index:
    """Okapi BM25 (k1 = 1.5, b = 0.75), Indonesian-aware tokenisation that keeps numbers like 13.500.000 whole."""
    def __init__(self, units, k1=1.5, b=0.75):
        self.units, self.k1, self.b = units, k1, b
        self.docs = [Counter(tokens(u["text"])) for u in units]
        self.len = [sum(c.values()) for c in self.docs]
        self.avg = sum(self.len) / max(1, len(self.len))
        df = Counter()
        for c in self.docs:
            df.update(c.keys())
        N = len(self.docs)
        self.idf = {t: math.log(1 + (N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
    def search(self, query, n):
        qt = tokens(query)
        scores = []
        for i, c in enumerate(self.docs):
            s = 0.0
            for t in qt:
                f = c.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            scores.append((s, i))
        scores.sort(key=lambda x: (-x[0], x[1]))
        return [i for _, i in scores[:min(n, len(scores))]]

class HybridIndex:
    """Reciprocal rank fusion of dense and BM25 rankings (Cormack et al., 2009), constant 60."""
    def __init__(self, dense, bm25, depth=50, c=60):
        self.dense, self.bm25, self.depth, self.c = dense, bm25, depth, c
        self.units = dense.units
    def search(self, query, n):
        score = defaultdict(float)
        for ranking in (self.dense.search(query, self.depth), self.bm25.search(query, self.depth)):
            for r, i in enumerate(ranking):
                score[i] += 1.0 / (self.c + r + 1)
        return [i for i, _ in sorted(score.items(), key=lambda x: (-x[1], x[0]))[:n]]

def build_index(units, retriever, embedder, use_chroma=False, cache=None):
    key = (id(units), retriever)
    if cache is not None and key in cache:
        return cache[key]
    if retriever == "bm25":
        idx = BM25Index(units)
    elif retriever == "dense":
        idx = DenseIndex(units, embedder, use_chroma)
    elif retriever == "hybrid":
        idx = HybridIndex(build_index(units, "dense", embedder, use_chroma, cache), build_index(units, "bm25", embedder, use_chroma, cache))
    else:
        raise ValueError(retriever)
    if cache is not None:
        cache[key] = idx
    return idx

# ----------------------------------------------------------------------------- LLMs
def text_of(content):
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)

class GeminiGenerator:
    def __init__(self, model, temperature=0.2):
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            sys.exit("GEMINI_API_KEY is not set (put it in .env)")
        self.model = model
        self.llm = ChatGoogleGenerativeAI(model=model, temperature=temperature, google_api_key=key)
        self.last_ms, self.retries = None, 0
    def _invoke(self, prompt, timeout=90):
        # the gRPC call can hang indefinitely on 503s; bound each attempt so it is retried instead
        out = {}
        def run():
            try:
                out["r"] = self.llm.invoke(prompt)
            except Exception as e:
                out["e"] = e
        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            raise TimeoutError(f"no response within {timeout}s")
        if "e" in out:
            raise out["e"]
        return out["r"]
    def __call__(self, prompt):
        # last_ms = duration of the successful call only, so rate-limit back-off never inflates latency
        self.retries = 0
        for attempt in range(8):
            try:
                t = time.perf_counter()
                out = text_of(self._invoke(prompt).content).strip()
                self.last_ms = round(1000 * (time.perf_counter() - t), 1)
                return out
            except Exception as e:
                self.retries += 1
                wait = min(2 ** attempt * 5, 120)
                print(f"[gen] {e.__class__.__name__}: {str(e)[:120]} | retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError("generation failed after retries (check the API quota)")

class MockGenerator:
    model = "mock-echo"
    last_ms, retries = 0.0, 0
    def __call__(self, prompt):
        m = re.search(r"\n\n(.*)\n\nPertanyaan:", prompt, re.S)
        ctx = m.group(1).strip() if m else ""
        return ctx[:300] if ctx else "Informasi tidak ditemukan."

JUDGE_PROMPT = """You are grading answers from an Indonesian university-information chatbot.
Return ONLY a JSON object, no other text.

Question: {question}
Reference answer: {reference}
Question is answerable from the knowledge base: {answerable}
Retrieved context given to the chatbot:
<<<
{context}
>>>
Chatbot answer: {answer}

Fields:
- "refusal": true if the chatbot declined or said the information was not found, else false.
- "correctness": for an answerable question, 2 = all key facts of the reference are present and nothing contradicts it,
  1 = partly correct or incomplete, 0 = wrong, contradicting, or a refusal. For an unanswerable question,
  2 = the chatbot refused or said it could not find the information, 0 = it gave a substantive answer.
- "faithfulness": 1 if every factual claim in the answer is supported by the retrieved context, 0 if any claim is not;
  null if there is no retrieved context or the answer is a refusal.
- "rationale": one short sentence.
"""

class CohereJudge:
    def __init__(self, model):
        import cohere
        key = os.getenv("COHERE_API_KEY")
        if not key:
            sys.exit("COHERE_API_KEY is not set (put it in .env)")
        self.client, self.model = cohere.ClientV2(api_key=key), model
    def raw(self, prompt):
        for attempt in range(6):
            try:
                r = self.client.chat(model=self.model, messages=[{"role": "user", "content": prompt}], temperature=0)
                return r.message.content[0].text
            except Exception as e:
                wait = 2 ** attempt * 5
                print(f"[judge] {e.__class__.__name__}: retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError("judge failed after retries")

class GeminiJudge:
    def __init__(self, model):
        self.g = GeminiGenerator(model, temperature=0.0)
        self.model = model
    def raw(self, prompt):
        return self.g(prompt)

class MockJudge:
    model = "mock-heuristic"
    def raw(self, prompt):
        return "{}"

def parse_judge(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        j = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        j = {}
    return j

def pure_refusal(answer):
    """True when the answer is only the prescribed refusal sentence (no substantive content)."""
    a = re.sub(r"[^\w\s]", " ", answer.lower())
    a = re.sub(r"\s+", " ", a).strip()
    return a.startswith(REFUSAL) and len(a) <= len(REFUSAL) + 25

def apply_refusal_rule(rec):
    """A pure refusal is scored by rule: 0 for an answerable question, 2 for an unanswerable one.
    The LLM judge sometimes credits refusals to answerable questions when it sees no context."""
    if rec.get("judge_correctness_raw") is None and "judge_correctness" in rec:
        rec["judge_correctness_raw"] = rec["judge_correctness"]
    if pure_refusal(rec.get("answer", "")):
        rec["judge_correctness"] = 0 if rec["answerable"] else 2
        rec["judge_faithfulness"] = None
        rec["judge_refusal"] = True
        rec["refusal_rule_applied"] = rec["judge_correctness"] != rec.get("judge_correctness_raw")
    else:
        rec["refusal_rule_applied"] = False
    return rec

def judge(judge_model, item, answer, context, mock=False):
    refused_rule = REFUSAL in answer.lower()
    if mock:
        f1 = token_f1(answer, item["reference_answer"])
        if not item["answerable"]:
            corr = 2 if refused_rule else 0
        else:
            corr = 0 if refused_rule else (2 if f1 >= 0.5 else 1 if f1 >= 0.2 else 0)
        faith = None if (refused_rule or not context) else int(norm(answer)[:60] in norm(context))
        return dict(refusal=refused_rule, correctness=corr, faithfulness=faith, rationale="mock", raw="")
    prompt = JUDGE_PROMPT.format(question=item["question"], reference=item["reference_answer"],
                                 answerable="yes" if item["answerable"] else "no",
                                 context=context if context else "(none)", answer=answer)
    raw = judge_model.raw(prompt)
    j = parse_judge(raw)
    corr = j.get("correctness")
    corr = int(corr) if isinstance(corr, (int, float)) and corr in (0, 1, 2) else None
    faith = j.get("faithfulness")
    faith = int(faith) if isinstance(faith, (int, float)) and faith in (0, 1) else None
    return dict(refusal=bool(j.get("refusal", refused_rule)), correctness=corr, faithfulness=faith,
                rationale=str(j.get("rationale", ""))[:300], raw=raw[:2000])

# ----------------------------------------------------------------------------- statistics
def bootstrap_ci(values, n=1000, seed=42):
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]

def mcnemar_exact(a, b):
    """Two-sided exact McNemar test on paired binary outcomes; returns (b01, b10, p)."""
    b01 = sum(1 for x, y in zip(a, b) if not x and y)
    b10 = sum(1 for x, y in zip(a, b) if x and not y)
    n = b01 + b10
    if n == 0:
        return b01, b10, 1.0
    k = min(b01, b10)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return b01, b10, min(1.0, 2 * p)

def cohen_kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in labels) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0

def pct(xs):
    return 100.0 * sum(xs) / len(xs) if xs else float("nan")

def percentile(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)

# ----------------------------------------------------------------------------- environment record
def env_record(args, extra=None):
    rec = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), python=sys.version.split()[0],
               platform=platform.platform(), processor=platform.processor() or platform.machine(),
               cpu_count=os.cpu_count(), args={k: v for k, v in vars(args).items() if k != "func"})
    pk = {}
    for name in ("cohere", "chromadb", "langchain_google_genai", "langchain_text_splitters", "numpy"):
        try:
            from importlib.metadata import version
            pk[name] = version(name.replace("_", "-"))
        except Exception:
            pk[name] = None
    rec["packages"] = pk
    if extra:
        rec.update(extra)
    return rec

# ----------------------------------------------------------------------------- commands
def get_embedder(args):
    return HashEmbedder() if args.mock else CohereEmbedder(args.embed_model, os.path.join(args.out, "cache"))

def cmd_check(args):
    docs = load_raw_corpus(args.repo)
    items = load_testset(args.testset)
    naive = naive_units(docs)
    cunits, cstats = clean_units(docs, args.chunk_size, args.overlap)
    raw_norm = {d["id"]: norm(d["text"]) for d in docs}
    naive_norm = [norm(u["text"]) for u in naive]
    clean_norm = [norm(u["text"]) for u in cunits]
    tot_chars = sum(len(d["text"].strip()) for d in docs)
    kept_chars = sum(len(u["text"]) for u in naive)
    print(f"corpus: {len(docs)} source documents, {tot_chars:,} characters")
    print(f"naive index: {len(naive)} units, {kept_chars:,} characters kept ({100 * kept_chars / tot_chars:.1f}%), "
          f"{sum(1 for d in docs if len(d['text'].strip()) > TRUNC)} documents truncated")
    print(f"clean index: {dict(cstats)}")
    rows, problems = [], 0
    for it in items:
        if not it["answerable"]:
            continue
        evs = it["evidence"]
        in_raw = [any(evidence_in(t, e) for t in raw_norm.values()) for e in evs]
        in_naive = all(any(evidence_in(t, e) for t in naive_norm) for e in evs)
        in_clean = all(any(evidence_in(t, e) for t in clean_norm) for e in evs)
        if not all(in_raw):
            problems += 1
            print(f"[MISSING] {it['id']} evidence not found in corpus: {[e for e, ok in zip(evs, in_raw) if not ok]}")
        rows.append((it, in_naive, in_clean))
    ans = [r for r in rows]
    print(f"\nanswerable items: {len(ans)}; evidence reachable in naive index: "
          f"{sum(r[1] for r in ans)} ({pct([r[1] for r in ans]):.1f}%); in clean index: "
          f"{sum(r[2] for r in ans)} ({pct([r[2] for r in ans]):.1f}%)")
    lost = [r[0]["id"] for r in ans if not r[1]]
    print(f"items whose evidence the deployed 3,000-character truncation removes: {len(lost)} {lost}")
    split_lost = [r[0]["id"] for r in ans if not r[2]]
    if split_lost:
        print(f"[warn] evidence split across clean chunks (or removed): {split_lost}")
    print(f"unanswerable items: {sum(1 for it in items if not it['answerable'])}")
    by = Counter(it["category"] for it in items)
    print("by category:", dict(by))
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "check.json"), "w", encoding="utf-8") as f:
        json.dump(dict(corpus_docs=len(docs), corpus_chars=tot_chars, naive_units=len(naive), naive_chars=kept_chars,
                       naive_truncated_docs=sum(1 for d in docs if len(d["text"].strip()) > TRUNC),
                       clean=dict(cstats), answerable=len(ans), unanswerable=sum(1 for it in items if not it["answerable"]),
                       reachable_naive=sum(r[1] for r in ans), reachable_clean=sum(r[2] for r in ans),
                       lost_by_truncation=lost, categories=dict(by), missing_evidence=problems), f, indent=2)
    return 1 if problems else 0

def retrieval_metrics(idx, units, items, ks, depth=10):
    units_norm = [norm(u["text"]) for u in units]
    out = {k: defaultdict(list) for k in ks}
    for it in items:
        if not it["answerable"]:
            continue
        ranked = idx.search(it["question"], max(max(ks), depth))
        rel = [any(evidence_in(units_norm[i], e) for e in it["evidence"]) for i in ranked]
        first = next((r for r, x in enumerate(rel[:depth]) if x), None)
        for k in ks:
            top = ranked[:k]
            union = " ".join(units_norm[i] for i in top)
            covered = [evidence_in(union, e) for e in it["evidence"]]
            out[k]["ids"].append(it["id"])
            out[k]["hit"].append(any(rel[:k]))
            out[k]["ev_recall"].append(sum(covered) / len(covered))
            out[k]["ev_hit"].append(all(covered))
            out[k]["mrr"].append(0.0 if first is None else 1.0 / (first + 1))
            out[k]["ctx_chars"].append(sum(len(units[i]["text"]) for i in top))
    return out

def cmd_retrieval(args):
    docs = load_raw_corpus(args.repo)
    items = load_testset(args.testset)
    retrievers = args.retrievers.split(",")
    emb = get_embedder(args) if any(r in ("dense", "hybrid") for r in retrievers) else None
    ks = [int(x) for x in args.ks.split(",")]
    rows, perq = [], {}
    settings = [("naive", None)] + [("clean", int(cs)) for cs in args.chunk_sizes.split(",")]
    for ingestion, cs in settings:
        units = naive_units(docs) if ingestion == "naive" else clean_units(docs, cs, args.overlap)[0]
        cache = {}
        for retriever in retrievers:
            t0 = time.time()
            idx = build_index(units, retriever, emb, args.index == "chroma", cache)
            m = retrieval_metrics(idx, units, items, ks)
            for k in ks:
                perq[(ingestion, cs or "", retriever, k)] = dict(zip(m[k]["ids"], m[k]["ev_hit"]))
                rows.append(dict(ingestion=ingestion, chunk_size=cs or "", units=len(units), retriever=retriever, k=k,
                                 n=len(m[k]["hit"]), hit=pct(m[k]["hit"]), mrr10=100 * statistics.mean(m[k]["mrr"]),
                                 evidence_recall=100 * statistics.mean(m[k]["ev_recall"]),
                                 evidence_hit=pct(m[k]["ev_hit"]),
                                 evidence_hit_ci=bootstrap_ci([float(x) for x in m[k]["ev_hit"]]),
                                 ctx_chars=statistics.mean(m[k]["ctx_chars"])))
            print(f"{ingestion:5} cs={cs or '-':>5} {retriever:6} done in {time.time() - t0:.1f}s", file=sys.stderr)
    # paired exact McNemar test of evidence hit against the deployed setting (naive ingestion, dense, same k)
    base_ret = "dense" if "dense" in retrievers else retrievers[0]
    for r in rows:
        base = perq.get(("naive", "", base_ret, r["k"]))
        cur = perq[(r["ingestion"], r["chunk_size"], r["retriever"], r["k"])]
        if base is None or base is cur:
            r.update(vs_deployed_gained="", vs_deployed_lost="", mcnemar_p="")
            continue
        ids = sorted(base)
        b01, b10, p = mcnemar_exact([base[i] for i in ids], [cur[i] for i in ids])
        r.update(vs_deployed_gained=b01, vs_deployed_lost=b10, mcnemar_p=p)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "retrieval_per_question.jsonl"), "w", encoding="utf-8") as f:
        for (ing, cs, ret, k), d in perq.items():
            for qid, v in d.items():
                f.write(json.dumps(dict(ingestion=ing, chunk_size=cs, retriever=ret, k=k, id=qid, evidence_hit=bool(v))) + "\n")
    with open(os.path.join(args.out, "retrieval.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            r = dict(r, evidence_hit_ci=f"{100 * r['evidence_hit_ci'][0]:.1f}-{100 * r['evidence_hit_ci'][1]:.1f}")
            w.writerow({k: (f"{v:.4f}" if k == "mcnemar_p" and isinstance(v, float) else f"{v:.2f}" if isinstance(v, float) else v)
                        for k, v in r.items()})
    with open(os.path.join(args.out, "retrieval_env.json"), "w") as f:
        json.dump(env_record(args, dict(embed_model="hash-mock" if args.mock else args.embed_model)), f, indent=2)
    print(f"wrote {os.path.join(args.out, 'retrieval.csv')} ({len(rows)} rows)")

def cmd_generation(args):
    docs = load_raw_corpus(args.repo)
    items = load_testset(args.testset)
    if args.limit:
        items = items[:args.limit]
    emb = get_embedder(args) if not all(c == "G0" for c in args.configs.split(",")) else None
    gen = MockGenerator() if args.mock else GeminiGenerator(args.gen_model)
    if args.mock:
        jdg = MockJudge()
    elif args.judge_provider == "cohere":
        jdg = CohereJudge(args.judge_model)
    else:
        jdg = GeminiJudge(args.judge_model)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "generation.jsonl")
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for l in f:
                r = json.loads(l)
                done[(r["config"], r["id"])] = r
    unit_sets, idx_cache, unit_norms = {}, {}, {}
    with open(path, "a", encoding="utf-8") as fout:
        for cfg_name in args.configs.split(","):
            cfg = GEN_CONFIGS[cfg_name]
            idx = None
            if cfg["ingestion"]:
                key = cfg["ingestion"]
                if key not in unit_sets:
                    unit_sets[key] = build_units(docs, key, args.chunk_size, args.overlap)
                    unit_norms[key] = [norm(u["text"]) for u in unit_sets[key]]
                idx = build_index(unit_sets[key], cfg["retriever"], emb, args.index == "chroma", idx_cache)
            for it in items:
                prev = done.get((cfg_name, it["id"]))
                if prev and prev["question"] == it["question"] and prev["reference"] == it["reference_answer"]:
                    continue  # already answered; a revised question or reference is answered again
                t0 = time.perf_counter()
                if idx is not None:
                    top = idx.search(it["question"], cfg["k"])
                    ctx_units = [idx.units[i] for i in top]
                    context = "\n\n".join(u["text"] for u in ctx_units)  # LangChain "stuff" separator
                    prompt = RAG_PROMPT.format(context=context, question=it["question"])
                else:
                    ctx_units, context = [], ""
                    prompt = LLM_ONLY_PROMPT.format(question=it["question"])
                t1 = time.perf_counter()
                answer = gen(prompt)
                t2 = time.perf_counter()
                j = judge(jdg, it, answer, context, mock=args.mock)
                ctx_norm = norm(context)
                rec = dict(config=cfg_name, id=it["id"], category=it["category"], answerable=it["answerable"],
                           question=it["question"], reference=it["reference_answer"], answer=answer,
                           retrieved=[u["id"] for u in ctx_units],
                           evidence_in_context=(all(evidence_in(ctx_norm, e) for e in it["evidence"]) if it["answerable"] and idx is not None else None),
                           evidence_in_index=(all(any(evidence_in(t, e) for t in unit_norms[cfg["ingestion"]]) for e in it["evidence"])
                                              if it["answerable"] and idx is not None else None),
                           retrieval_ms=round(1000 * (t1 - t0), 1), generation_ms=round(1000 * (t2 - t1), 1),
                           generation_call_ms=gen.last_ms, gen_retries=gen.retries,
                           refusal_rule=REFUSAL in answer.lower(), token_f1=round(token_f1(answer, it["reference_answer"]), 4),
                           gen_model=gen.model, judge_model=jdg.model, **{f"judge_{k}": v for k, v in j.items()})
                rec = apply_refusal_rule(rec)
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fout.flush()
                done[(cfg_name, it["id"])] = rec
                print(f"{cfg_name} {it['id']} corr={rec['judge_correctness']} faith={rec['judge_faithfulness']}", file=sys.stderr)
                if args.sleep:
                    time.sleep(args.sleep)
    with open(os.path.join(args.out, "generation_env.json"), "w") as f:
        json.dump(env_record(args, dict(gen_model=gen.model, judge_model=jdg.model,
                                        embed_model="hash-mock" if args.mock else args.embed_model)), f, indent=2)
    write_human_sample(args, load_generation(args.out, args.testset))
    print(f"wrote {path}")

def write_human_sample(args, recs, per_config=None):
    """Blinded sample: the same questions answered by the deployed (G1) and best clean (G4) systems, shuffled.
    The annotation sheet carries no configuration or judge label; those go to a separate key file that the
    annotator should not open until scoring is finished."""
    rng = random.Random(7)
    by_cfg = defaultdict(dict)
    for r in recs:
        by_cfg[r["config"]][r["id"]] = r
    cfgs = [c for c in ("G1", "G4") if c in by_cfg] or list(by_cfg)[:2]
    if not cfgs:
        return
    ids = sorted(set.intersection(*(set(by_cfg[c]) for c in cfgs)))
    rng.shuffle(ids)
    ids = ids[:args.human_n]
    rows, keys = [], []
    for qid in ids:
        for c in cfgs:
            r = by_cfg[c][qid]
            item = sha1(c + qid)[:10]
            rows.append(dict(item=item, question=r["question"], reference=r["reference"], answer=r["answer"],
                             annotator_1="", annotator_2=""))
            keys.append(dict(item=item, config=c, id=qid, answerable=r["answerable"], judge=r.get("judge_correctness")))
    rng.shuffle(rows)
    p = os.path.join(args.out, "human_eval_sample.csv")
    kp = os.path.join(args.out, "human_eval_key.csv")
    if os.path.exists(p):
        # never overwrite a sheet that may already hold scores; the key is rewritten (same seed, same items)
        print(f"[keep] {p} already exists and was not overwritten (delete it to draw a new sample)")
        targets = ((kp, keys),)
    else:
        targets = ((p, rows), (kp, keys))
    for path, data in targets:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader(); w.writerows(data)
    if len(targets) == 2:
        print(f"wrote {p}: {len(rows)} answers to score 0/1/2 in column annotator_1 (annotator_2 only if a second person scores). "
              f"Do not open {os.path.basename(kp)} before you finish scoring.")

def cmd_human_sample(args):
    recs = load_generation(args.out, args.testset)
    if not recs:
        sys.exit("no generation.jsonl in --out; run the generation command first")
    write_human_sample(args, recs)

def weighted_kappa(a, b, labels=(0, 1, 2)):
    """Quadratic-weighted Cohen's kappa for ordinal scores."""
    n = len(a)
    if n == 0:
        return float("nan")
    L = len(labels); idx = {l: i for i, l in enumerate(labels)}
    w = [[(i - j) ** 2 / (L - 1) ** 2 for j in range(L)] for i in range(L)]
    O = [[0] * L for _ in range(L)]
    for x, y in zip(a, b):
        O[idx[x]][idx[y]] += 1
    ra = [sum(O[i]) for i in range(L)]; cb = [sum(O[i][j] for i in range(L)) for j in range(L)]
    num = sum(w[i][j] * O[i][j] for i in range(L) for j in range(L))
    den = sum(w[i][j] * ra[i] * cb[j] / n for i in range(L) for j in range(L))
    return 1 - num / den if den else 1.0

def load_generation(out, testset=None):
    """Latest record per (config, question). With a test set, keep only questions that are still in it
    unchanged, so removed or revised questions never leak into the tables."""
    p = os.path.join(out, "generation.jsonl")
    latest = {}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    r = json.loads(l)
                    latest[(r["config"], r["id"])] = r
    recs = [apply_refusal_rule(r) for r in latest.values()]
    if testset and os.path.exists(testset):
        cur = {it["id"]: it for it in load_testset(testset)}
        kept = [r for r in recs if r["id"] in cur and r["question"] == cur[r["id"]]["question"]
                and r["reference"] == cur[r["id"]]["reference_answer"]]
        if len(kept) < len(recs):
            print(f"[info] {len(recs) - len(kept)} stored answers ignored: their question was removed or revised "
                  f"(run generation again to answer revised questions)", file=sys.stderr)
        recs = kept
    return recs

def refresh_evidence(recs, args):
    """Recompute evidence_in_context / evidence_in_index from the stored retrieved unit ids and the
    current test set, so that edits to evidence spans never require re-running generation."""
    items = {it["id"]: it for it in load_testset(args.testset)}
    docs = load_raw_corpus(args.repo)
    unit_text = {}
    for ing in {GEN_CONFIGS[r["config"]]["ingestion"] for r in recs if r["config"] in GEN_CONFIGS} - {None}:
        units = build_units(docs, ing, args.chunk_size, args.overlap)
        unit_text[ing] = ({u["id"]: norm(u["text"]) for u in units}, [norm(u["text"]) for u in units])
    for r in recs:
        it, ing = items.get(r["id"]), GEN_CONFIGS.get(r["config"], {}).get("ingestion")
        if not it or not it["answerable"] or not ing:
            continue
        by_id, all_norm = unit_text[ing]
        ctx = " ".join(by_id.get(u, "") for u in r.get("retrieved", []))
        r["evidence_in_context"] = all(evidence_in(ctx, e) for e in it["evidence"])
        r["evidence_in_index"] = all(any(evidence_in(t, e) for t in all_norm) for e in it["evidence"])
    return recs

def latencies(rs):
    """Retrieval + successful generation call, in ms. Older records without generation_call_ms
    include rate-limit back-off and are left out."""
    clean = [r["retrieval_ms"] + r["generation_call_ms"] for r in rs if r.get("generation_call_ms") is not None]
    return clean

def generation_summary(recs):
    by = defaultdict(list)
    for r in recs:
        by[r["config"]].append(r)
    rows = []
    base = {r["id"]: (r["judge_correctness"] == 2) for r in by.get("G1", []) if r["answerable"]}
    for c in sorted(by):
        rs = by[c]
        ans = [r for r in rs if r["answerable"]]
        una = [r for r in rs if not r["answerable"]]
        acc = [float(r["judge_correctness"] == 2) for r in ans if r["judge_correctness"] is not None]
        part = [float((r["judge_correctness"] or 0) >= 1) for r in ans if r["judge_correctness"] is not None]
        faith = [float(r["judge_faithfulness"]) for r in ans if r["judge_faithfulness"] is not None]
        lo, hi = bootstrap_ci(acc)
        row = dict(config=c, label=GEN_CONFIGS.get(c, {}).get("label", c), n_answerable=len(ans), n_unanswerable=len(una),
                   accuracy=pct(acc), accuracy_ci=f"{100 * lo:.1f}-{100 * hi:.1f}", partial_or_better=pct(part),
                   faithfulness=pct(faith) if (faith and GEN_CONFIGS.get(c, {}).get("ingestion")) else float("nan"),
                   false_refusal=pct([float(r["judge_refusal"] or r["refusal_rule"]) for r in ans]),
                   negative_rejection=pct([float(r["judge_correctness"] == 2) for r in una]) if una else float("nan"),
                   token_f1=100 * statistics.mean([r["token_f1"] for r in ans]) if ans else float("nan"),
                   evidence_in_context=pct([float(r["evidence_in_context"]) for r in ans if r["evidence_in_context"] is not None]) if c != "G0" else float("nan"),
                   latency_p50_ms=percentile(latencies(rs), 0.5),
                   latency_p95_ms=percentile(latencies(rs), 0.95),
                   latency_n=len(latencies(rs)),
                   refusal_rule_overrides=sum(1 for r in rs if r.get("refusal_rule_applied")))
        if base and c != "G1":
            paired = [(base[r["id"]], r["judge_correctness"] == 2) for r in ans if r["id"] in base]
            b01, b10, p = mcnemar_exact([a for a, _ in paired], [b for _, b in paired])
            row.update(vs_G1_gained=b01, vs_G1_lost=b10, mcnemar_p=p)
        rows.append(row)
    # Holm-Bonferroni adjustment across the comparisons with G1
    cmp_rows = sorted([r for r in rows if "mcnemar_p" in r], key=lambda r: r["mcnemar_p"])
    m, running = len(cmp_rows), 0.0
    for i, r in enumerate(cmp_rows):
        running = max(running, min(1.0, (m - i) * r["mcnemar_p"]))
        r["mcnemar_p_holm"] = running
    return rows

PLANNED = [("G1", "G0", "value of retrieval"), ("G2", "G1", "ingestion"), ("G3", "G2", "retriever"), ("G4", "G3", "depth")]

def planned_comparisons(recs):
    """The paired comparisons of Table 4 (each isolates one factor), exact McNemar, Holm-adjusted."""
    acc = defaultdict(dict)
    for r in recs:
        if r["answerable"] and r["judge_correctness"] is not None:
            acc[r["config"]][r["id"]] = r["judge_correctness"] == 2
    out = []
    for a, b, factor in PLANNED:
        if a not in acc or b not in acc:
            continue
        ids = sorted(set(acc[a]) & set(acc[b]))
        b01, b10, p = mcnemar_exact([acc[b][i] for i in ids], [acc[a][i] for i in ids])
        out.append(dict(comparison=f"{a} vs {b}", factor=factor, n=len(ids), acc_a=pct([acc[a][i] for i in ids]),
                        acc_b=pct([acc[b][i] for i in ids]), gained=b01, lost=b10, p=p))
    running = 0.0
    for i, r in enumerate(sorted(out, key=lambda r: r["p"])):
        running = max(running, min(1.0, (len(out) - i) * r["p"]))
        r["p_holm"] = running
    return out

def failure_type(r):
    """Failure taxonomy aligned with Barnett et al. (2024): FP1 missing content, FP2/FP3 not retrieved, FP4/FP7 not extracted."""
    if not r["answerable"]:
        return "Answered an unanswerable question"
    if r.get("evidence_in_index") is False:
        return "Missing content (evidence not indexed)"
    if r.get("evidence_in_context") is False:
        return "Not retrieved (indexed, not in top k)"
    if r.get("judge_refusal") or r.get("refusal_rule"):
        return "Refused although evidence was in context"
    return "Wrong or incomplete although evidence was in context"

def fmt(v, d=1):
    if isinstance(v, float):
        return "–" if math.isnan(v) else f"{v:.{d}f}"
    return str(v)

def cmd_report(args):
    lines = [f"# Evaluation results\n\nGenerated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from `{args.out}`.\n"]
    cp = os.path.join(args.out, "check.json")
    if os.path.exists(cp):
        c = json.load(open(cp))
        lines += ["## Corpus and test set\n",
                  f"- Source documents: {c['corpus_docs']}; characters: {c['corpus_chars']:,}",
                  f"- Naive index keeps {c['naive_chars']:,} characters ({100 * c['naive_chars'] / c['corpus_chars']:.1f}%); {c['naive_truncated_docs']} documents truncated",
                  f"- Clean ingestion: {c['clean']}",
                  f"- Test set: {c['answerable']} answerable + {c['unanswerable']} unanswerable questions",
                  f"- Answerable questions whose evidence survives naive ingestion: {c['reachable_naive']} ({100 * c['reachable_naive'] / c['answerable']:.1f}%); clean ingestion: {c['reachable_clean']} ({100 * c['reachable_clean'] / c['answerable']:.1f}%)\n"]
    rp = os.path.join(args.out, "retrieval.csv")
    if os.path.exists(rp):
        rows = list(csv.DictReader(open(rp, encoding="utf-8")))
        lines += ["## Retrieval (answerable questions)\n",
                  "| Ingestion | Chunk (chars) | Units | Retriever | k | Hit@k (%) | MRR@10 (%) | Evidence recall@k (%) | Evidence hit@k (%) [95% CI] | Context (chars) | vs deployed: gained / lost, McNemar p |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            mc = (f"{r['vs_deployed_gained']} / {r['vs_deployed_lost']}, p = {float(r['mcnemar_p']):.4f}"
                  if r.get("mcnemar_p") not in (None, "") else "–")
            lines.append(f"| {r['ingestion']} | {r['chunk_size'] or '–'} | {r['units']} | {r['retriever']} | {r['k']} | {float(r['hit']):.1f} | {float(r['mrr10']):.1f} | {float(r['evidence_recall']):.1f} | {float(r['evidence_hit']):.1f} [{r['evidence_hit_ci']}] | {float(r['ctx_chars']):.0f} | {mc} |")
        lines.append("")
    recs = load_generation(args.out, args.testset)
    if recs:
        recs = refresh_evidence(recs, args)
        rows = generation_summary(recs)
        lines += ["## End-to-end answer quality\n",
                  "| Config | Description | Accuracy (%) [95% CI] | Partial or better (%) | Faithfulness (%) | False refusal (%) | Negative rejection (%) | Token F1 | Evidence in context (%) | p50 / p95 latency (s) | vs G1: gained / lost, McNemar p (Holm) |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            mc = f"{r['vs_G1_gained']} / {r['vs_G1_lost']}, p = {r['mcnemar_p']:.3f} ({r['mcnemar_p_holm']:.3f})" if "mcnemar_p" in r else "–"
            lines.append(f"| {r['config']} | {r['label']} | {fmt(r['accuracy'])} [{r['accuracy_ci']}] | {fmt(r['partial_or_better'])} | {fmt(r['faithfulness'])} | {fmt(r['false_refusal'])} | {fmt(r['negative_rejection'])} | {fmt(r['token_f1'])} | {fmt(r['evidence_in_context'])} | {r['latency_p50_ms'] / 1000:.2f} / {r['latency_p95_ms'] / 1000:.2f} | {mc} |")
        lines.append("\nPure refusals rescored by rule (judge label overridden): "
                     + "; ".join(f"{r['config']} {r['refusal_rule_overrides']}" for r in rows)
                     + ". Latency counts only records with a measured successful call: "
                     + "; ".join(f"{r['config']} n = {r['latency_n']}" for r in rows) + ".")
        pc = planned_comparisons(recs)
        if pc:
            lines += ["\n## Planned paired comparisons (answerable questions, exact McNemar, Holm-adjusted)\n",
                      "| Comparison | Factor isolated | n | Accuracy A (%) | Accuracy B (%) | Gained / lost | p | p (Holm) |",
                      "|---|---|---|---|---|---|---|---|"]
            for r in pc:
                lines.append(f"| {r['comparison']} | {r['factor']} | {r['n']} | {r['acc_a']:.1f} | {r['acc_b']:.1f} | {r['gained']} / {r['lost']} | {r['p']:.4f} | {r['p_holm']:.4f} |")
        by_cat = defaultdict(lambda: defaultdict(list))
        for r in recs:
            if r["judge_correctness"] is not None:
                by_cat[r["category"]][r["config"]].append(float(r["judge_correctness"] == 2))
        cfgs = sorted({r["config"] for r in recs})
        lines += ["\n## Accuracy by category (%)\n", "| Category | n | " + " | ".join(cfgs) + " |", "|---|---|" + "---|" * len(cfgs)]
        for cat in sorted(by_cat):
            n = max(len(v) for v in by_cat[cat].values())
            lines.append(f"| {cat} | {n} | " + " | ".join(fmt(pct(by_cat[cat][c])) if by_cat[cat][c] else "–" for c in cfgs) + " |")
        fail = defaultdict(Counter)
        for r in recs:
            if r["config"] == "G0" or r["judge_correctness"] is None or r["judge_correctness"] == 2:
                continue
            fail[r["config"]][failure_type(r)] += 1
        types = ["Missing content (evidence not indexed)", "Not retrieved (indexed, not in top k)",
                 "Refused although evidence was in context", "Wrong or incomplete although evidence was in context",
                 "Answered an unanswerable question"]
        rag_cfgs = [c for c in cfgs if c != "G0"]
        lines += ["\n## Failure analysis (questions not fully correct)\n", "| Failure type | " + " | ".join(rag_cfgs) + " |", "|---|" + "---|" * len(rag_cfgs)]
        for t in types:
            lines.append(f"| {t} | " + " | ".join(str(fail[c][t]) for c in rag_cfgs) + " |")
        env = os.path.join(args.out, "generation_env.json")
        if os.path.exists(env):
            e = json.load(open(env))
            lines += [f"\nGenerator: `{e.get('gen_model')}`; judge: `{e.get('judge_model')}`; embedder: `{e.get('embed_model')}`; "
                      f"Python {e['python']} on {e['platform']}."]
    p = os.path.join(args.out, "tables.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {p}")

def cmd_kappa(args):
    # Excel with Indonesian regional settings saves CSV with ';' and may add a BOM
    with open(args.file, encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        rows = list(csv.DictReader(f, delimiter=delim))
    def score(v):
        v = (v or "").strip()
        return int(float(v.replace(",", "."))) if v else None
    # judge labels: from the key file (new format) or from the _judge column (older sheets)
    key = {}
    kp = args.key or os.path.join(os.path.dirname(os.path.abspath(args.file)), "human_eval_key.csv")
    if os.path.exists(kp):
        with open(kp, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                key[r["item"]] = r
    out = []
    for r in rows:
        a1 = score(r.get("annotator_1"))
        if a1 is None:
            continue
        a2 = score(r.get("annotator_2"))
        k = key.get(r["item"], {})
        j = k.get("judge", r.get("_judge"))
        j = score(j) if j not in (None, "", "None") else None
        out.append(dict(a1=a1, a2=a2, judge=j, config=k.get("config", r.get("_config", "?"))))
    print(f"scored items: {len(out)}")
    two = [o for o in out if o["a2"] is not None]
    if two:
        a, b = [o["a1"] for o in two], [o["a2"] for o in two]
        print(f"annotator 1 vs 2 on {len(two)} items: kappa {cohen_kappa(a, b):.3f}, weighted kappa {weighted_kappa(a, b):.3f}, "
              f"raw agreement {pct([x == y for x, y in zip(a, b)]):.1f}%")
    # human label: consensus where two annotators agree, otherwise annotator 1 alone
    hum = [(o["a1"] if o["a2"] is None else (o["a1"] if o["a1"] == o["a2"] else None), o) for o in out]
    pairs = [(h, o["judge"]) for h, o in hum if h is not None and o["judge"] is not None]
    if not pairs:
        print("no judge labels found: put human_eval_key.csv next to the sheet or pass --key")
        return
    h, j = [p[0] for p in pairs], [p[1] for p in pairs]
    hb, jb = [int(x == 2) for x in h], [int(x == 2) for x in j]
    print(f"human vs LLM judge on {len(pairs)} items (0/1/2): kappa {cohen_kappa(h, j):.3f}, weighted kappa {weighted_kappa(h, j):.3f}, "
          f"raw agreement {pct([x == y for x, y in zip(h, j)]):.1f}%")
    print(f"human vs LLM judge on 'fully correct' (the accuracy metric): kappa {cohen_kappa(hb, jb):.3f}, "
          f"raw agreement {pct([x == y for x, y in zip(hb, jb)]):.1f}%")
    by = defaultdict(lambda: ([], []))
    for hv, o in hum:
        if hv is not None and o["judge"] is not None:
            by[o["config"]][0].append(int(hv == 2)); by[o["config"]][1].append(int(o["judge"] == 2))
    for c in sorted(by):
        hs, js = by[c]
        print(f"  {c}: fully correct by human {pct(hs):.1f}% vs by judge {pct(js):.1f}% (n = {len(hs)})")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=os.path.abspath(os.path.join(HERE, "..")), help="repository root (contains data_telkom.json and data/)")
    ap.add_argument("--testset", default=os.path.join(HERE, "testset_telu.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("--mock", action="store_true", help="offline smoke test: hashing embedder, echo generator, heuristic judge")
    ap.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "embed-v4.0"))
    ap.add_argument("--gen-model", default=os.getenv("GEN_MODEL", "gemini-2.5-flash"),
                    help="the deployed gemini-2.0-flash has a Google shutdown date of 1 June 2026; report the model you actually ran")
    ap.add_argument("--judge-provider", choices=["cohere", "gemini"], default=os.getenv("JUDGE_PROVIDER", "cohere"),
                    help="a judge from a different model family than the generator reduces self-preference bias")
    ap.add_argument("--judge-model", default=os.getenv("JUDGE_MODEL", "command-a-03-2025"))
    ap.add_argument("--index", choices=["numpy", "chroma"], default="numpy", help="dense search backend (exact L2 or in-memory Chroma)")
    ap.add_argument("--chunk-size", type=int, default=1000)
    ap.add_argument("--overlap", type=int, default=150)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    r = sub.add_parser("retrieval")
    r.add_argument("--retrievers", default="dense,bm25,hybrid")
    r.add_argument("--ks", default="1,3,5,10")
    r.add_argument("--chunk-sizes", default="500,1000,1500")
    r.set_defaults(func=cmd_retrieval)
    g = sub.add_parser("generation")
    g.add_argument("--configs", default="G0,G1,G2,G3,G4")
    g.add_argument("--limit", type=int, default=0)
    g.add_argument("--sleep", type=float, default=0.0, help="seconds between calls (free-tier rate limits)")
    g.add_argument("--human-n", type=int, default=40, help="questions in the blinded human-evaluation sample")
    g.set_defaults(func=cmd_generation)
    sub.add_parser("report").set_defaults(func=cmd_report)
    h = sub.add_parser("human-sample", help="(re)build the blinded annotation sheet from an existing generation.jsonl")
    h.add_argument("--human-n", type=int, default=40)
    h.set_defaults(func=cmd_human_sample)
    k = sub.add_parser("kappa")
    k.add_argument("--file", required=True)
    k.add_argument("--key", default="", help="human_eval_key.csv (default: next to --file)")
    k.set_defaults(func=cmd_kappa)
    args = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(args.repo, ".env"))
    except ImportError:
        pass
    sys.exit(args.func(args) or 0)

if __name__ == "__main__":
    main()
