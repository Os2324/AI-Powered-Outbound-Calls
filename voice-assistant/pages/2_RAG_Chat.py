"""
RAG chat + knowledge-base management, living inside the same app as the
voice assistant. Reuses the chatbot project's retrieve/build_context/ask_llm
and ingest logic directly (same functions server.py already uses for calls),
so this is the same knowledge base and same answering pipeline -- just with
a chat UI plus the ability to upload a new document and re-index on demand.

Logging + feedback reuse the chatbot's own db.py (same logs.db file), so
every RAG interaction -- whether asked here or in the chatbot's own app --
ends up in one unified log.
"""

import os
import sys
import time
import importlib.util

import streamlit as st

CHATBOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "chatbot"))
sys.path.append(CHATBOT_DIR)  # append, not insert(0), so local files still win on name clashes

from query import retrieve, build_context, ask_llm, EMBEDDING_MODEL, COLLECTION_NAME, LLM_API_KEY, LLM_BASE_URL  # noqa: E402
from ingest import run_ingestion, DATA_DIR  # noqa: E402

import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI


def _load_module(name, path):
    """Loads a module by explicit file path -- avoids the fact that both
    projects have their own, different db.py, which a plain `import db`
    could accidentally resolve to the wrong one."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


chatbot_db = _load_module("chatbot_db", os.path.join(CHATBOT_DIR, "db.py"))
chatbot_db.init_db()

st.set_page_config(page_title="قاعدة المعرفة", page_icon="📚", layout="centered")

st.markdown(
    """
    <style>
    .stApp { background: #ffffff; }
    .block-container { max-width: 760px; padding-top: 2rem; direction: rtl; }
    .kb-hero {
        background: linear-gradient(120deg, #fdba74 0%, #f97316 65%, #c2410c 100%);
        border-radius: 20px; padding: 26px 24px; margin-bottom: 20px;
        color: #ffffff; text-align: center;
    }
    .kb-hero h1 { margin: 0; font-size: 1.5rem; }
    div[data-testid="stChatMessage"] { background: transparent !important; border: none !important; box-shadow: none !important; }
    .source-row { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #fed7aa; font-size: 0.78rem; color: #78716c; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="kb-hero"><h1>📚 قاعدة المعرفة (RAG)</h1></div>', unsafe_allow_html=True)


@st.cache_resource(show_spinner="جاري تحميل نموذج التضمين...")
def load_resources():
    embed_model = SentenceTransformer(EMBEDDING_MODEL)
    llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    return embed_model, llm_client


embed_model, llm_client = load_resources()


def get_collection():
    db_dir = os.path.join(CHATBOT_DIR, "chroma_db")
    return chromadb.PersistentClient(path=db_dir).get_or_create_collection(COLLECTION_NAME)


# --- Document management -----------------------------------------------
with st.expander("📤 إدارة المستندات (رفع ملف جديد + إعادة الفهرسة)", expanded=False):
    uploaded = st.file_uploader("ارفع مستند جديد (txt, pdf, docx)", type=["txt", "pdf", "docx"])
    if uploaded is not None:
        os.makedirs(DATA_DIR, exist_ok=True)
        save_path = os.path.join(DATA_DIR, uploaded.name)
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.success(f"تم حفظ الملف: {uploaded.name}")

    if st.button("🔄 إعادة فهرسة كل المستندات", type="primary"):
        progress_box = st.empty()
        log_lines = []

        def on_progress(msg):
            log_lines.append(msg)
            progress_box.code("\n".join(log_lines))

        with st.spinner("جاري إعادة الفهرسة..."):
            result = run_ingestion(model=embed_model, progress_callback=on_progress)
        st.success(f"تم! {result['file_count']} ملف، {result['chunk_count']} جزء (chunk).")
        st.cache_resource.clear()

st.divider()

agent_name = st.text_input("اسمك (لتسجيل المتابعة)", key="rag_agent_name", placeholder="اكتب اسمك هنا...")

# --- Chat -----------------------------------------------------------------
if "kb_messages" not in st.session_state:
    st.session_state.kb_messages = []


def render_message(idx, msg):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] != "assistant":
            return

        sources = msg.get("sources", [])
        if sources:
            st.markdown(
                f'<div class="source-row">📄 المصادر: {", ".join(sources)}</div>',
                unsafe_allow_html=True,
            )

        feedback = msg.get("feedback")
        if feedback:
            st.caption("👍 شكرًا لتقييمك!" if feedback == "up" else "👎 شكرًا لملاحظتك!")
        else:
            col1, col2, _ = st.columns([1, 1, 8])
            with col1:
                if st.button("👍", key=f"kb_up_{idx}"):
                    chatbot_db.set_feedback(msg["row_id"], "up")
                    st.session_state.kb_messages[idx]["feedback"] = "up"
                    st.rerun()
            with col2:
                if st.button("👎", key=f"kb_down_{idx}"):
                    chatbot_db.set_feedback(msg["row_id"], "down")
                    st.session_state.kb_messages[idx]["feedback"] = "down"
                    st.rerun()


for i, msg in enumerate(st.session_state.kb_messages):
    render_message(i, msg)

question = st.chat_input("اسأل عن أي شيء في قاعدة المعرفة...")

if question:
    st.session_state.kb_messages.append({"role": "user", "content": question})
    render_message(len(st.session_state.kb_messages) - 1, st.session_state.kb_messages[-1])

    with st.spinner("جاري البحث والإجابة..."):
        try:
            start_time = time.time()
            collection = get_collection()
            results = retrieve(question, collection, embed_model)
            context = build_context(results)
            answer = ask_llm(question, context, llm_client)
            latency = time.time() - start_time
            sources = sorted({meta["source"] for _, meta in results})
            row_id = chatbot_db.log_interaction(agent_name or "غير معروف", question, answer, sources, latency)
        except Exception as e:
            answer = f"حدث خطأ: {e}"
            sources = []
            row_id = None

    st.session_state.kb_messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "row_id": row_id,
            "feedback": None,
        }
    )
    render_message(len(st.session_state.kb_messages) - 1, st.session_state.kb_messages[-1])
