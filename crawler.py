import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
from tqdm import tqdm

# Config
domain = "telkomuniversity.ac.id"
output_file = "data_telkom.json"
max_depth = 1
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Load cache if exists
visited = set()
data = []

if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            visited = {item["url"] for item in data}
            print(f"🗂 Loaded {len(data)} data dari file sebelumnya.\n")
        except Exception:
            print("⚠️ File JSON rusak, mulai ulang dari awal.")

# Crawl function
def crawl(url, depth=0):
    if depth > max_depth or url in visited:
        return
    visited.add(url)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"❌ {url} [Status: {response.status_code}]")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)

        if len(text) > 100:
            record = {
                "url": url,
                "content": text
            }
            data.append(record)

            # Save langsung agar tidak hilang
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"✅ Crawled: {url} [total: {len(data)}]")

        # Crawl link lain dalam halaman
        for link in soup.find_all("a", href=True):
            href = urljoin(url, link["href"])
            parsed = urlparse(href)
            if domain in parsed.netloc and parsed.scheme.startswith("http"):
                crawl(href, depth + 1)

    except Exception as e:
        print(f"❌ Error at {url}: {e}")

# Start URLs
start_urls = [
    "https://ailo.telkomuniversity.ac.id/",
    "https://smb.telkomuniversity.ac.id/",
    "https://baa.telkomuniversity.ac.id/"

  
  
]

# Run crawler dengan progress
print("🚀 Memulai crawling...\n")
for start_url in tqdm(start_urls, desc="📡 Crawling Subdomain"):
    crawl(start_url)

print(f"\n✅ SELESAI. Total data disimpan: {len(data)} halaman.")