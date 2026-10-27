# Evaluasi Tiva (untuk artikel PeerJ Computer Science)

Folder ini menghasilkan semua angka yang di draf artikel masih bertanda ⟦RUN⟧.
Letakkan folder `eval/` di root repositori `chatbot_telu`, sejajar dengan `data_telkom.json` dan `data/`.

## Isi folder

| File | Fungsi |
| --- | --- |
| `evaluate.py` | Harness evaluasi: mereplikasi pipeline yang sedang jalan dan semua variannya |
| `testset_telu.jsonl` | 101 pertanyaan uji (89 bisa dijawab + 12 tidak bisa dijawab), **masih draf** |
| `testset_validation.csv` | Lembar validasi test set untuk dua anotator (buka di Excel) |
| `results_offline_bm25/` | Hasil offline (statistik korpus + retrieval BM25) yang sudah dimasukkan ke draf |

## Persiapan

1. Semua dependensi sudah ada di `requirements.txt` (cohere, chromadb, langchain-google-genai, langchain-text-splitters, numpy, python-dotenv).
2. Isi file `.env` di root repo:
   ```
   COHERE_API_KEY=...
   GEMINI_API_KEY=...
   ```
3. Uji tanpa API dulu (angkanya tidak bermakna, hanya memastikan semua jalan):
   ```
   python eval/evaluate.py --mock --out eval/results_mock retrieval
   python eval/evaluate.py --mock --out eval/results_mock generation --limit 5
   ```

## Langkah menjalankan

**0. Validasi test set (wajib sebelum menjalankan yang lain).**
Pertanyaan dan jawaban acuan disusun dari korpus dengan bantuan AI, jadi harus diperiksa manusia.
Buka `testset_validation.csv` dan periksa setiap baris terhadap halaman di kolom `source_urls`.
Isi `valid_annotator_1` dengan `ya`/`tidak`; kolom `valid_annotator_2` dibiarkan kosong kalau Anda menilai sendirian.
Tulis perbaikan di `corrected_question` / `corrected_answer`, dan catat berapa pertanyaan yang direvisi atau dibuang karena angka itu masuk ke artikel.
Terapkan perbaikan ke `testset_telu.jsonl`, lalu jalankan:
```
python eval/evaluate.py check
```
Perintah ini gagal jika ada `evidence` yang tidak ditemukan persis di korpus. Evidence harus berupa potongan teks asli.

**1. Retrieval (biaya: embedding Cohere saja).**
```
python eval/evaluate.py retrieval
```
Hasil: `eval/results/retrieval.csv` (Tabel 6 dan paragraf chunk size).

**2. End-to-end (Gemini + LLM judge).**
```
python eval/evaluate.py generation --sleep 6
```
Totalnya 5 konfigurasi × 101 pertanyaan = 505 jawaban + 505 penilaian judge.
Jika terputus, jalankan ulang perintah yang sama; yang sudah selesai tidak diulang.
`--sleep` mengatur jeda antarpanggilan untuk batas rate free tier.

- Generator default: `gemini-2.5-flash`. Model yang sedang dipakai, `gemini-2.0-flash`, tercantum dengan tanggal shutdown 1 Juni 2026 di halaman deprecation Google.
  Ganti dengan `--gen-model <nama>` dan **laporkan model yang benar-benar dipakai** di artikel.
- Judge default: Cohere `command-a-03-2025` (keluarga model berbeda dari generator). Alternatif: `--judge-provider gemini --judge-model <nama>`.

**3. Validasi judge oleh manusia (Anda sendiri sebagai anotator).**
Langkah 2 membuat dua file di `eval/results/`:
- `human_eval_sample.csv`: 80 jawaban (40 pertanyaan × G1 dan G4) dalam urutan acak, tanpa label konfigurasi dan tanpa skor judge.
- `human_eval_key.csv`: kunci (konfigurasi + skor judge). **Jangan dibuka sebelum selesai menilai**, supaya penilaian Anda tetap blind.

Isi kolom `annotator_1` dengan skor 0/1/2 dan biarkan `annotator_2` kosong. Rubriknya:
- **Pertanyaan yang bisa dijawab:** 2 = semua fakta kunci benar dan tidak ada yang bertentangan dengan acuan; 1 = sebagian benar atau kurang lengkap; 0 = salah, bertentangan, atau menolak menjawab.
- **Pertanyaan yang tidak bisa dijawab** (acuannya "Informasi tidak ditemukan."): 2 = sistem menolak; 0 = sistem tetap memberi jawaban.

Lalu jalankan:
```
python eval/evaluate.py kappa --file eval/results/human_eval_sample.csv
```
Perintah ini membaca kunci secara otomatis dan menampilkan kappa, weighted kappa, dan persentase kesepakatan Anda dengan judge.
Hasil "fully correct" adalah yang paling penting, karena itulah dasar metrik akurasi.
Kalau `generation` dijalankan dengan versi kit yang lama, buat ulang lembar blind-nya dengan `python eval/evaluate.py human-sample`
(hapus dulu `human_eval_sample.csv` yang lama, kecuali sudah ada nilainya).

**4. Tabel untuk artikel.**
```
python eval/evaluate.py report
```
Hasil: `eval/results/tables.md`.

| Bagian di `tables.md` | Masuk ke artikel |
| --- | --- |
| Corpus and test set | Abstract, RQ1 (periksa ulang setelah test set divalidasi) |
| Retrieval | Tabel 6 dan paragraf chunk size |
| End-to-end answer quality | Tabel 7, Abstract, Conclusions |
| Accuracy by category | Teks RQ3 (opsional jadi tabel tambahan) |
| Failure analysis | Tabel 8 |
| Output perintah `kappa` | Paragraf *Human validation* dan *Judge validity* |

Platform, versi Python, versi paket dan nama model setiap run tercatat otomatis di `results/*_env.json`.
Bagian *Computing infrastructure* di PeerJ mewajibkan informasi ini.

## Konfigurasi yang dibandingkan

| Kode | Ingestion | Retriever | k |
| --- | --- | --- | --- |
| G0 | – | Tanpa retrieval (LLM saja) | 0 |
| G1 | Naive (seperti yang sedang jalan) | Dense (Cohere) | 3 |
| G2 | Clean | Dense | 3 |
| G3 | Clean | Hybrid (RRF dense + BM25) | 3 |
| G4 | Clean | Hybrid | 5 |

Opsi lain: `--index chroma` memakai koleksi Chroma in-memory (default: pencarian L2 eksak dengan numpy).
`--chunk-size` / `--overlap` mengatur chunking untuk G2–G4.
