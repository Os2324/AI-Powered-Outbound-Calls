"""
Web chat UI for the KB chatbot, built with Streamlit.
Reuses the same retrieve/build_context/ask_llm logic from query.py —
this file is just the visual layer on top of that existing pipeline.

Run with: venv\\Scripts\\python.exe -m streamlit run app.py
"""

import time

import streamlit as st
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI

from query import (
    DB_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    LLM_API_KEY,
    LLM_BASE_URL,
    retrieve,
    build_context,
    ask_llm,
)
from db import init_db, log_interaction, set_feedback

init_db()

st.set_page_config(page_title="المساعد الداخلي", page_icon="💬", layout="centered")

# --- Styling: bright, playful, RTL chat bubble look -------------------------
st.markdown(
    """
    <style>
    .stApp {
        background: #ffffff;
    }
    /* RTL is scoped to the main content only, so Streamlit's own sidebar
       toggle and chrome keep their normal (working) positioning. */
    .block-container { max-width: 740px; padding-top: 2rem; direction: rtl; }
    header[data-testid="stHeader"] { background: transparent; }
    div[data-testid="stChatInput"] { direction: rtl; }

    .app-hero {
        background: linear-gradient(120deg, #7dd3fc 0%, #38bdf8 100%);
        border-radius: 20px;
        padding: 32px 24px;
        margin-bottom: 24px;
        color: #ffffff;
        text-align: center;
        box-shadow: 0 10px 30px -12px rgba(56, 189, 248, 0.6);
    }
    .app-hero h1 { margin: 0; font-size: 1.75rem; }
    .app-hero p { margin: 8px 0 0; opacity: 0.95; font-size: 0.95rem; }

    /* Chat messages: no boxes, just clean text with a soft blue accent per role */
    div[data-testid="stChatMessage"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 4px 6px;
        margin-bottom: 18px;
    }
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] li,
    div[data-testid="stChatMessage"] span,
    div[data-testid="stChatMessage"] ol,
    div[data-testid="stChatMessage"] ul {
        color: #0f172a !important;
    }
    div[data-testid="stChatMessage"]:nth-of-type(odd) p,
    div[data-testid="stChatMessage"]:nth-of-type(odd) li,
    div[data-testid="stChatMessage"]:nth-of-type(odd) span {
        color: #0369a1 !important;
    }
    .source-tag, .source-tag * { color: #0284c7 !important; }

    .source-row {
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px dashed #bae6fd;
    }
    .source-label {
        font-size: 0.78rem;
        color: #64748b;
        margin-inline-end: 8px;
    }
    .source-tag {
        display: inline-block;
        background: #e0f2fe;
        color: #0284c7;
        border: 1px solid #7dd3fc;
        border-radius: 999px;
        padding: 4px 14px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-inline-end: 6px;
    }

    div[data-testid="stChatInput"] {
        border-radius: 16px;
        box-shadow: 0 4px 16px -6px rgba(56, 189, 248, 0.4);
    }

    /* Sidebar + its collapse/expand arrow: match the light-blue theme */
    section[data-testid="stSidebar"] {
        background: #f0f9ff;
        border-right: 1px solid #bae6fd;
    }
    [data-testid="stSidebarCollapsedControl"] {
        background: #e0f2fe;
        border: 1px solid #7dd3fc;
        border-radius: 10px;
        padding: 4px;
        top: 14px;
    }
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] path {
        color: #0284c7 !important;
        fill: #0284c7 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="app-hero">
        <h1>🤖 المساعد الداخلي لخدمة العملاء</h1>
        <p>اسأل أي سؤال متعلق بإجراءات الشركة، وسأجيبك اعتمادًا على الدليل الداخلي فقط</p>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="جاري تحميل النظام...")
def load_resources():
    embed_model = SentenceTransformer(EMBEDDING_MODEL)
    db_client = chromadb.PersistentClient(path=DB_DIR)
    collection = db_client.get_collection(COLLECTION_NAME)
    llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    return embed_model, collection, llm_client


if not LLM_API_KEY:
    st.error("LLM_API_KEY غير موجود. تأكد من إضافته في ملف .env")
    st.stop()

embed_model, collection, llm_client = load_resources()

agent_name = st.text_input(
    "أدخل اسمك",
    key="agent_name",
    placeholder="اكتب اسمك هنا...",
)

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_message(idx, msg):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] != "assistant":
            return

        sources = msg.get("sources", [])
        tags = "".join(f'<span class="source-tag">📄 {s}</span>' for s in sources)
        st.markdown(
            f'<div class="source-row"><span class="source-label">المصادر:</span>{tags}</div>',
            unsafe_allow_html=True,
        )

        feedback = msg.get("feedback")
        if feedback:
            st.caption("👍 تقييم إيجابي، شكرًا لك!" if feedback == "up" else "👎 تقييم سلبي، شكرًا لملاحظتك!")
        else:
            col1, col2, _ = st.columns([1, 1, 8])
            with col1:
                if st.button("👍", key=f"up_{idx}"):
                    set_feedback(msg["row_id"], "up")
                    st.session_state.messages[idx]["feedback"] = "up"
                    st.rerun()
            with col2:
                if st.button("👎", key=f"down_{idx}"):
                    set_feedback(msg["row_id"], "down")
                    st.session_state.messages[idx]["feedback"] = "down"
                    st.rerun()


for i, msg in enumerate(st.session_state.messages):
    render_message(i, msg)

question = st.chat_input("اكتب سؤالك هنا...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    render_message(len(st.session_state.messages) - 1, st.session_state.messages[-1])

    with st.spinner("جاري البحث في المستندات..."):
        start_time = time.time()
        results = retrieve(question, collection, embed_model)
        context = build_context(results)
        answer = ask_llm(question, context, llm_client)
        latency = time.time() - start_time
        sources = sorted({meta["source"] for _, meta in results})
        row_id = log_interaction(agent_name or "غير معروف", question, answer, sources, latency)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "row_id": row_id,
            "feedback": None,
        }
    )
    render_message(len(st.session_state.messages) - 1, st.session_state.messages[-1])
