# entrypoint.py
from load_to_chroma import build_chroma
build_chroma()

from app import app
app.run(host="0.0.0.0", port=5000)
