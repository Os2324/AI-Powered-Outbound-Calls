"""
Step 2 of the pipeline: retrieve relevant knowledge-base chunks and ask
the LLM to answer using only those chunks.

Also supports customizable response personas.

Usage:
    python query.py "ما هي خطوات تحديث بيانات العميل؟"
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI

load_dotenv()

DB_DIR = "chroma_db"
COLLECTION_NAME = "kb_docs"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
TOP_K = 4

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-flash-lite-latest")
LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = """أنت مساعد داخلي لموظفي خدمة العملاء. مهمتك الإجابة على الأسئلة اعتمادًا فقط على
المقتطفات المرفقة من الدليل الداخلي. لا تستخدم أي معلومات من خارج هذه المقتطفات.
إذا لم تجد إجابة واضحة في المقتطفات، قل بوضوح أن المعلومة غير متوفرة في المستندات المتاحة
واقترح تحويل السؤال لمشرف. أجب دائمًا باللغة العربية بإيجاز ووضوح، واذكر اسم المصدر
(اسم الملف) الذي استخرجت منه الإجابة."""

PERSONAS = {
    "professional": {
        "name": "رسمي",
        "instruction": "أجب بأسلوب رسمي ومهني وواضح.",
    },
    "friendly": {
        "name": "ودود",
        "instruction": "أجب بأسلوب ودود ولطيف وبسيط مع الحفاظ على المهنية.",
    },
    "concise": {
        "name": "مختصر",
        "instruction": "أجب بأقصر إجابة ممكنة مع الحفاظ على المعلومات المهمة.",
    },
}


# ---------------------------------------------------------------------------
# RAG retrieval
# ---------------------------------------------------------------------------

def retrieve(question, collection, model):
    query_embedding = model.encode(
        [f"query: {question}"]
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=TOP_K,
    )

    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]

    return list(zip(chunks, metadatas))


def build_context(chunks_with_meta):
    parts = []

    for chunk, meta in chunks_with_meta:
        parts.append(
            f"[المصدر: {meta['source']}]\n{chunk}"
        )

    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def ask_llm(question, context, client, persona="professional"):
    persona_config = PERSONAS.get(
        persona,
        PERSONAS["professional"],
    )

    system_prompt = (
        DEFAULT_SYSTEM_PROMPT
        + "\n\n"
        + "أسلوب الإجابة المطلوب:\n"
        + persona_config["instruction"]
    )

    user_prompt = (
        f"المقتطفات:\n\n{context}\n\n"
        f"السؤال: {question}"
    )

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Command-line test
# ---------------------------------------------------------------------------

def main():
    if not LLM_API_KEY:
        print("ERROR: LLM_API_KEY not set. Add it to .env.")
        return

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("اكتب سؤالك: ")

    print("Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    client_db = chromadb.PersistentClient(path=DB_DIR)

    try:
        collection = client_db.get_collection(COLLECTION_NAME)
    except Exception:
        print("No collection found. Run `python ingest.py` first.")
        return

    print("Retrieving relevant chunks...")
    results = retrieve(
        question,
        collection,
        model,
    )

    context = build_context(results)

    print("Asking the LLM (via Gemini)...\n")

    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )

    # Default persona for command-line testing.
    answer = ask_llm(
        question,
        context,
        client,
        persona="professional",
    )

    print("=" * 50)
    print(answer)
    print("=" * 50)

    print(
        "\nRetrieved from:",
        ", ".join(
            sorted(
                {m["source"] for _, m in results}
            )
        ),
    )


if __name__ == "__main__":
    main()