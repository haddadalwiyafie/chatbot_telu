# Tiva: RAG chatbot for Telkom University admissions

Code, test set and evaluation results for Tiva, a retrieval-augmented chatbot that answers questions about Telkom University
(admissions, fees, programmes, campus life) from the university's public web pages.

Authors: Agus Pratondo, Haddad Alwi Yafie, Muhammad Sheva Atallah Daffansyah (Telkom University).
Funded by Penelitian Strategis (Invitasi) Tematik Artificial Intelligence (AI) Tahun 2025.

## Contents

| Path | Description |
| --- | --- |
| `crawler.py` | Crawls `telkomuniversity.ac.id` (depth 1) into `data_telkom.json` |
| `load_to_chroma.py`, `generate_to_chroma.py` | Deployed ingestion: one Cohere `embed-v4.0` vector per page (first 3,000 characters) into Chroma |
| `langchain_pipeline.py`, `app.py` | Deployed RAG pipeline (Chroma, k = 3, Gemini) behind a Flask `/chat` endpoint with bearer-token auth |
| `corpus_urls.txt` | Source URLs of the corpus |
| `eval/evaluate.py` | Evaluation harness: retrieval metrics, end-to-end answers with an LLM judge, report tables, human-judge agreement |
| `eval/testset_telu.jsonl` | Test set: 101 questions (89 answerable, 12 unanswerable) with reference answers and verbatim evidence |
| `eval/testset_validation_annotated.csv` | Human validation of the test set |
| `eval/results/` | Results reported in the article (`tables.md`, per-question answers and judge scores, environment files, `kappa_output.txt`) |

## Data

The corpus text is not redistributed. `corpus_urls.txt` lists every source page: the pages crawled by `crawler.py`
(late July to early August 2025) and the pages compiled manually into `data/hala_web.csv`. Re-running `crawler.py` rebuilds
`data_telkom.json` from the live site, whose content may have changed since the snapshot.

## Running

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt    # Python 3.12
cp .env.example .env                                                  # add your API keys
.venv/bin/python crawler.py
.venv/bin/python -c "from load_to_chroma import build_chroma; build_chroma()"
.venv/bin/python app.py
```

Evaluation (see `eval/README.md` for details):

```
.venv/bin/python eval/evaluate.py check
.venv/bin/python eval/evaluate.py retrieval
.venv/bin/python eval/evaluate.py --gen-model gemini-3.5-flash-lite generation --sleep 10
.venv/bin/python eval/evaluate.py report
```

## License

Code: MIT. Test set, validation sheets and evaluation results in `eval/` (except `eval/evaluate.py`): CC BY 4.0. See `LICENSE`.
