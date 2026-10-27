
import os
import cohere
import csv
from chromadb import PersistentClient
from dotenv import load_dotenv

load_dotenv()

co = cohere.Client(os.getenv("COHERE_API_KEY"))
client = PersistentClient(path="./chroma_db_baru")
collection = client.get_or_create_collection(name="telu_docs")


def embed_and_add(text, source, doc_id):
    text = text.strip()[:3000]
    if not text:
        return
    
    response = co.embed(
        texts=[text],
        input_type="search_document",
        model="embed-v4.0"
    )
    
    # NOTE: Di v4, ambil embedding dari `.embeddings` langsung
    embedding = response.embeddings[0] if hasattr(response, 'embeddings') else response[0]

    collection.add(
        documents=[text],
        embeddings=[embedding],
        metadatas=[{"source": source}],
        ids=[doc_id]
    )
    print(f"✅ Masuk: {source} ({doc_id})")

def detect_text_columns(headers):
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
    else:
        return "", ""

def process_csv_auto(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        sample = f.read(5000)
        delimiter = ";" if ";" in sample else ","
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delimiter)
        headers = reader.fieldnames
        col1, col2 = detect_text_columns(headers)

        print(f"📄 Proses CSV: {os.path.basename(file_path)} | Kolom: {col1}, {col2}")

        for i, row in enumerate(reader):
            text = f"{row.get(col1, '')}\n{row.get(col2, '')}"
            if not text.strip():
                continue
            embed_and_add(text, source=file_path, doc_id=f"{os.path.basename(file_path)}-{i}")

def process_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        print(f"📄 Proses TXT: {os.path.basename(file_path)}")
        embed_and_add(content, source=file_path, doc_id=f"{os.path.basename(file_path)}-0")

def process_all_in_folder(folder_path="data"):
    if not os.path.exists(folder_path):
        print(f"❌ Folder tidak ditemukan: {folder_path}")
        return

    for filename in os.listdir(folder_path):
        path = os.path.join(folder_path, filename)
        if os.path.isfile(path):
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".csv":
                process_csv_auto(path)
            elif ext == ".txt":
                process_txt(path)

    print("✅ Semua file di folder 'data' telah diproses.")

if __name__ == "__main__":
    process_all_in_folder("data")
