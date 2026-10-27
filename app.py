from flask import Flask, request, jsonify

from langchain_pipeline import ask_question
from dotenv import load_dotenv
from flask_cors import CORS


import os

load_dotenv()
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
app = Flask(__name__)
CORS(app)

@app.before_request
def authenticate():
    if request.method == "OPTIONS":
        return
    
    if request.path == "/chat":
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization token missing"}), 401
        token = auth_header.split("Bearer ")[1].strip()
        if token != AUTH_TOKEN:
            return jsonify({"error": "Invalid token"}), 403
        
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "Pertanyaan tidak boleh kosong"}), 400

    try:
        answer = ask_question(question)
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)