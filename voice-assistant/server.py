"""
Webhook server for the outbound-call voice assistant.

Vonage calls POST /speech-response whenever it recognizes something the
customer said mid-call. This decides how to respond:
  - If it's an answer to the yes/no/uncertain verification question, reply
    accordingly (thank & close, or offer help/transfer).
  - If it's an unrelated question, look up a real answer using the SAME
    RAG pipeline (retrieve + ask_llm) and knowledge base the chatbot project
    already built, instead of just deferring to a human.

Either way, it returns a new NCCO (Vonage's call-instruction format) telling
Vonage what to say back, live, in the same call.

Run with: venv\\Scripts\\python.exe server.py
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from sentence_transformers import SentenceTransformer

# Reuse the chatbot project's RAG pipeline directly instead of duplicating it.
CHATBOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chatbot"))
sys.path.insert(0, CHATBOT_DIR)
from query import retrieve, build_context, ask_llm, EMBEDDING_MODEL, COLLECTION_NAME  # noqa: E402

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-flash-lite-latest")
LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
CHROMA_DB_DIR = os.path.join(CHATBOT_DIR, "chroma_db")

CLASSIFY_PROMPT = """أنت تصنف رد عميل في مكالمة متابعة هاتفية. المكالمة تسأل العميل هل أتم خطوات
معينة تمت مناقشتها في مكالمة سابقة. صنّف رد العميل إلى واحد فقط من هذه التصنيفات:
- yes: العميل يؤكد أنه أتم الخطوات
- no: العميل يقول إنه لم يتمها
- unsure: العميل غير متأكد
- question: العميل يسأل سؤالاً مختلفاً تمامًا وليس إجابة عن السؤال
رد بكلمة واحدة فقط من: yes, no, unsure, question"""

print("Loading embedding model and knowledge base...")
embed_model = SentenceTransformer(EMBEDDING_MODEL)
kb_collection = chromadb.PersistentClient(path=CHROMA_DB_DIR).get_collection(COLLECTION_NAME)
llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
print("Ready.")

app = Flask(__name__)


def classify_response(customer_text):
    response = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": CLASSIFY_PROMPT},
            {"role": "user", "content": customer_text},
        ],
        temperature=0,
    )
    label = response.choices[0].message.content.strip().lower()
    for known in ("yes", "no", "unsure", "question"):
        if known in label:
            return known
    return "unsure"


def verification_reply(label):
    if label == "yes":
        return "ممتاز جداً! شكراً لتعاونك معنا، ونتمنى لك يوماً سعيداً. مع السلامة!"
    if label == "no":
        return "لا يهمك خالص، هل تحب أحولك لموظف من خدمة العملاء يساعدك في الخطوات دي؟"
    return "فهمت عليك، هل تحب أحولك لأحد زملائي في خدمة العملاء ليتابع معك؟"


def rag_reply(question):
    results = retrieve(question, kb_collection, embed_model)
    context = build_context(results)
    return ask_llm(question, context, llm_client)


@app.route("/speech-response", methods=["POST"])
def speech_response():
    data = request.get_json(force=True, silent=True) or {}
    print("Incoming speech webhook payload:", data)

    results = data.get("speech", {}).get("results", [])
    customer_text = results[0]["text"] if results else ""

    if not customer_text:
        ncco = [{"action": "talk", "text": "معلش مسمعتش حضرتك كويس، ممكن تعيد تاني؟", "language": "ar"}]
        return jsonify(ncco)

    label = classify_response(customer_text)
    print(f"Customer said: {customer_text!r} -> classified as: {label}")

    if label == "question":
        reply_text = rag_reply(customer_text)
    else:
        reply_text = verification_reply(label)

    print(f"Replying: {reply_text!r}")
    ncco = [{"action": "talk", "text": reply_text, "language": "ar"}]
    return jsonify(ncco)


@app.route("/event", methods=["POST"])
def event():
    data = request.get_json(force=True, silent=True) or {}
    print("Call event:", data.get("status"))
    return "", 200


if __name__ == "__main__":
    app.run(port=5000)
