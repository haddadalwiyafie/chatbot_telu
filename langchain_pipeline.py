import os
from dotenv import load_dotenv
import cohere
from langchain_community.vectorstores import Chroma
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# LangChain LLM pakai Gemini
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.2,
    timeout=60,
    max_retries=2,
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# Custom embedder pakai Cohere
class CustomCohereEmbedder:
    def __init__(self):
        self.client = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))

    def embed_documents(self, texts):
        response = self.client.embed(
            texts=texts,
            input_type="search_document",
            model="embed-v4.0"
        )
        # Ambil embeddings langsung dari response
        return response.embeddings

    def embed_query(self, text):
        response = self.client.embed(
            texts=[text],
            input_type="search_query",
            model="embed-v4.0"
        )
        return response.embeddings[0]

embedding = CustomCohereEmbedder()

# Load vector dari ChromaDB
vectorstore = Chroma(
    persist_directory="./chroma_db_baru",
    collection_name="telu_docs",
    embedding_function=embedding
)

retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# Prompt
prompt_template = PromptTemplate(
    input_variables=["context", "question"],
    template="""
Gunakan informasi berikut untuk menjawab pertanyaan secara ringkas, detail, langsung, dan dalam Bahasa Indonesia.
Jika tidak ditemukan jawabannya, cukup katakan "Informasi tidak ditemukan."

{context}

Pertanyaan: {question}
Jawaban:
"""
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    chain_type="stuff",
    chain_type_kwargs={"prompt": prompt_template},
    return_source_documents=False
)

def ask_question(question: str):
    return qa_chain.run(question)
