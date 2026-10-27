
import os
import json
import time
from chromadb import PersistentClient
from dotenv import load_dotenv
import cohere

def build_chroma(json_path="data_telkom.json", chroma_path="./chroma_db_baru"):
    load_dotenv()
    cohere_api_key = os.getenv("COHERE_API_KEY")

    if not cohere_api_key:
        print("❌ COHERE_API_KEY tidak ditemukan di .env.")
        return

    co = cohere.Client(cohere_api_key)

    if not os.path.exists(json_path):
        print(f"❌ File {json_path} tidak ditemukan.")
        return

    print(f"📁 Membuka file {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            documents = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Gagal membaca JSON: {e}")
            return

    print(f"📦 Memulai proses embedding untuk {len(documents)} dokumen..")
    client = PersistentClient(path=chroma_path)

    try:
        collection = client.get_or_create_collection(name="telu_docs")
    except Exception as e:
        print(f"❌ Gagal membuat/mendapatkan koleksi Chroma: {e}")
        return

    for i, doc in enumerate(documents):
        content = doc.get("content", "")[:3000]
        if not content.strip():
            print(f"⚠️ Dokumen ke-{i+1} kosong, dilewati.")
            continue

        try:
            print(f"🔄 [{i+1}/{len(documents)}] Embedding dokumen...")
            embedding_response = co.embed(
                texts=[content],
                input_type="search_document",
                model="embed-v4.0"  # Gantilah jika kamu pakai embed-multilingual-v3.0
            )
            embedding = embedding_response.embeddings[0]
            print(f"✅ [{i+1}] Berhasil embedding.")

            collection.add(
                documents=[content],
                embeddings=[embedding],
                metadatas=[{"url": doc.get("url", "")}],
                ids=[f"doc-{i}"]
            )
            print(f"📥 [{i+1}] Ditambahkan ke koleksi Chroma.\n")
        except Exception as e:
            print(f"❌ [{i+1}] Gagal embed/tambah ke Chroma: {e}")
            continue

        # Opsional: beri jeda agar tidak ke rate limit saat batch besar
        time.sleep(0.3)

    print("🎉 Selesai memproses semua dokumen.")
