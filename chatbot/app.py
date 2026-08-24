"""
Web chat + voice UI for the KB RAG chatbot.

Supports:
- Text questions
- Voice questions using browser microphone + Whisper STT
- Voice answers using gTTS TTS
- Customizable response personas
- Source citations
- Feedback logging
"""

import time
from pathlib import Path

import streamlit as st
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from router import route_question, create_client
from sql_query import process_sql_question
TOP_K = 4
from query import (
    DB_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    LLM_API_KEY,
    LLM_BASE_URL,
    PERSONAS,
    retrieve,
    build_context,
    ask_llm,
)

from db import (
    init_db,
    log_interaction,
    set_feedback,
)

from voice import (
    transcribe_audio,
    text_to_speech,
)

from router import route_question
from sql_query import process_sql_question




init_db()

st.set_page_config(
    page_title="المساعد الداخلي",
    page_icon="💬",
    layout="centered",
)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp {
        background: #ffffff;
    }

    .block-container {
        max-width: 740px;
        padding-top: 2rem;
        direction: rtl;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    div[data-testid="stChatInput"] {
        direction: rtl;
    }

    .app-hero {
        background: linear-gradient(120deg, #7dd3fc 0%, #38bdf8 100%);
        border-radius: 20px;
        padding: 32px 24px;
        margin-bottom: 24px;
        color: #ffffff;
        text-align: center;
        box-shadow: 0 10px 30px -12px rgba(56, 189, 248, 0.6);
    }

    .app-hero h1 {
        margin: 0;
        font-size: 1.75rem;
    }

    .app-hero p {
        margin: 8px 0 0;
        opacity: 0.95;
        font-size: 0.95rem;
    }

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

    .source-tag,
    .source-tag * {
        color: #0284c7 !important;
    }

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


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="app-hero">
        <h1>🤖 المساعد الداخلي لخدمة العملاء</h1>
        <p>
            اسأل أي سؤال متعلق بإجراءات الشركة،
            وسأجيبك اعتمادًا على الدليل الداخلي فقط
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Load RAG resources
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="جاري تحميل النظام...")
def load_resources():
    embed_model = SentenceTransformer(EMBEDDING_MODEL)

    db_client = chromadb.PersistentClient(path=DB_DIR)

    collection = db_client.get_collection(COLLECTION_NAME)

    llm_client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )

    return embed_model, collection, llm_client


if not LLM_API_KEY:
    st.error("LLM_API_KEY غير موجود. تأكد من إضافته في ملف .env")
    st.stop()


embed_model, collection, llm_client = load_resources()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ إعدادات المساعد")

    agent_name = st.text_input(
        "أدخل اسمك",
        key="agent_name",
        placeholder="اكتب اسمك هنا...",
    )

    persona_options = list(PERSONAS.keys())

    selected_persona = st.selectbox(
        "اختر أسلوب الإجابة",
        options=persona_options,
        format_func=lambda key: PERSONAS[key]["name"],
        index=0,
    )

    st.markdown("---")

    st.markdown(
        """
        **🎤 الوضع الصوتي**

        سجل سؤالك باستخدام الميكروفون،
        وسيقوم النظام بتحويل كلامك إلى نص
        ثم البحث في قاعدة المعرفة وإعطاء
        الإجابة صوتيًا.
        """
    )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []


# ---------------------------------------------------------------------------
# Message renderer
# ---------------------------------------------------------------------------

def render_message(idx, msg):
    with st.chat_message(msg["role"]):

        st.markdown(msg["content"])

        if msg["role"] != "assistant":
            return

        # Sources
        sources = msg.get("sources", [])
        route = msg.get("route")

        if sources and route != "sql":

            tags = "".join(
                f'<span class="source-tag">📄 {s}</span>'
                for s in sources
            )

            st.markdown(
                f"""
                <div class="source-row">
                    <span class="source-label">المصادر:</span>
                    {tags}
                </div>
                """,
                unsafe_allow_html=True,
            )
                # SQL information
        route = msg.get("route")
        sql_query = msg.get("sql_query")

        if route == "sql":
            st.markdown(
                """
                <div class="source-row">
                    <span class="source-label">
                        المصدر:
                    </span>
                    <span class="source-tag">
                        🗄️ قاعدة البيانات
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if sql_query:
                with st.expander("🔍 عرض استعلام SQL"):
                    st.code(
                        sql_query,
                        language="sql",
                    )
        # Audio response
        audio_path = msg.get("audio_path")

        if audio_path and Path(audio_path).exists():
            st.audio(
                audio_path,
                format="audio/mp3",
            )

        # Feedback
        feedback = msg.get("feedback")

        if feedback:
            st.caption(
                "👍 تقييم إيجابي، شكرًا لك!"
                if feedback == "up"
                else "👎 تقييم سلبي، شكرًا لملاحظتك!"
            )
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


# ---------------------------------------------------------------------------
# Render previous messages
# ---------------------------------------------------------------------------

for i, msg in enumerate(st.session_state.messages):
    render_message(i, msg)


# ---------------------------------------------------------------------------
# RAG processing helper
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# RAG result filtering
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# RAG result filtering
# ---------------------------------------------------------------------------
def filter_relevant_results(results):
    """
    Remove weak/irrelevant RAG results.

    Chroma returns results ordered by similarity, so for now
    we keep the retrieved results while removing empty chunks.
    """

    filtered = []

    for chunk, meta in results:
        if not chunk:
            continue

        chunk = chunk.strip()

        if not chunk:
            continue

        filtered.append(
            (
                chunk,
                meta,
            )
        )

    return filtered
def process_question(question, generate_audio=False):
    """
    Run the complete hybrid RAG + SQL pipeline.

    question
        ↓
    router
      ├── SQL → Text-to-SQL → SQLite
      │
      └── RAG → ChromaDB → LLM
        ↓
    answer
        ↓
    optional TTS
    """

    start_time = time.time()
    route_start = time.time()

    # ---------------------------------------------------------
    # Decide whether this is SQL or RAG
    # ---------------------------------------------------------

    route = route_question(
        question,
        llm_client,
    )
    route_time = time.time() - route_start
    print(f"[DEBUG] Router: {route_time:.2f}s")
    sql_query = None
    sources = []

    # ---------------------------------------------------------
    # SQL route
    # ---------------------------------------------------------

    if route == "sql":
        sql_start = time.time()

        sql_query, _, _, answer = process_sql_question(
            question,
            llm_client,
        )

        sql_time = time.time() - sql_start
        print(f"[DEBUG] SQL pipeline: {sql_time:.2f}s")

        sources = ["قاعدة البيانات"]

    # ---------------------------------------------------------
    # RAG route
    # ---------------------------------------------------------

    else:
        rag_start = time.time()

        results = retrieve(
            question,
            collection,
            embed_model,
        )

        results = filter_relevant_results(
            results
        )

        context = build_context(results)

        answer = ask_llm(
            question,
            context,
            llm_client,
            persona=selected_persona,
        )

        rag_time = time.time() - rag_start
        print(f"[DEBUG] RAG pipeline: {rag_time:.2f}s")

        sources = sorted(
            {
                meta["source"]
                for _, meta in results
            }
        )

    # ---------------------------------------------------------
    # Latency
    # ---------------------------------------------------------

    latency = time.time() - start_time

    # ---------------------------------------------------------
    # Optional voice response
    # ---------------------------------------------------------

    audio_path = None

    if generate_audio:

        audio_dir = Path("generated_audio")
        audio_dir.mkdir(exist_ok=True)

        audio_path = (
            audio_dir
            / f"response_{int(time.time() * 1000)}.mp3"
        )

        text_to_speech(
            answer,
            audio_path,
        )

        audio_path = str(audio_path)

    # ---------------------------------------------------------
    # Logging
    # ---------------------------------------------------------

    row_id = log_interaction(
        agent_name or "غير معروف",
        question,
        answer,
        sources,
        latency,
    )

    return (
        answer,
        sources,
        row_id,
        audio_path,
        route,
        sql_query,
    )


# ---------------------------------------------------------------------------
# Voice input
# ---------------------------------------------------------------------------

st.markdown("### 🎤 اسأل بصوتك")

audio_value = st.audio_input(
    "اضغط هنا للتسجيل",
    key="voice_question",
)

if audio_value is not None:

    audio_file = Path("voice_input.wav")

    audio_file.write_bytes(
        audio_value.getvalue()
    )

    with st.spinner("🎧 جاري تحويل الصوت إلى نص..."):

        try:
            voice_question = transcribe_audio(
                audio_file
            )

        except Exception as exc:
            st.error(
                f"حدث خطأ أثناء تحويل الصوت إلى نص: {exc}"
            )
            voice_question = ""

    if voice_question:

        st.info(
            f"📝 النص الذي تم التعرف عليه: {voice_question}"
        )

        # Avoid processing the exact same recording repeatedly
        audio_hash = hash(audio_value.getvalue())

        if st.session_state.get("last_audio_hash") != audio_hash:

            st.session_state.last_audio_hash = audio_hash

            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": f"🎤 {voice_question}",
                }
            )

            with st.spinner(
                "🤖 جاري البحث في المستندات وإنشاء الإجابة..."
            ):

                answer, sources, row_id, audio_path, route, sql_query = process_question(
                    voice_question,
                    generate_audio=True,
                )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "row_id": row_id,
                    "feedback": None,
                    "audio_path": audio_path,
                    "route": route,
                    "sql_query": sql_query,
                }
            )

            st.rerun()


# ---------------------------------------------------------------------------
# Text input
# ---------------------------------------------------------------------------

question = st.chat_input(
    "اكتب سؤالك هنا..."
)

if question:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.spinner("جاري البحث في المستندات..."):

        answer, sources, row_id, audio_path, route, sql_query = process_question(
            question,
            generate_audio=False,
        )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "row_id": row_id,
            "feedback": None,
            "audio_path": audio_path,
            "route": route,
            "sql_query": sql_query,
        }
    )

    st.rerun()