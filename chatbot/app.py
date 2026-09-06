"""
Web chat UI for the KB chatbot, built with Streamlit.
Reuses the same retrieve/build_context/ask_llm logic from query.py —
this file is just the visual layer on top of that existing pipeline.

Now requires login and branches by role:
- super_admin: manages organizations and admin accounts (no chat -- not
  tied to any one organization's documents).
- admin: chat (scoped to their organization) + document upload/re-index +
  creating agent accounts for their organization.
- agent: chat only, scoped to their organization's documents.

Also supports:
- Voice questions (mic recording -> Whisper STT -> same RAG pipeline)
- Spoken answers (gTTS) when the question was asked by voice
- Customizable response personas
- Automatic routing to the SQL database for structured/data questions

Run with: venv\\Scripts\\python.exe -m streamlit run app.py
"""

import os
import time
import tempfile

import streamlit as st
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI

import auth
from auth_ui import require_login, render_logout_sidebar
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
from ingest import run_ingestion, ingest_single_file, get_org_data_dir
from db import init_db, log_interaction, set_feedback
from voice import transcribe_audio, text_to_speech
from router import route_question
from sql_query import process_sql_question

auth.init_auth_db()
init_db()

GENERATED_AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_audio")

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

if not LLM_API_KEY:
    st.error("LLM_API_KEY غير موجود. تأكد من إضافته في ملف .env")
    st.stop()

user = require_login()
render_logout_sidebar(user)


@st.cache_resource(show_spinner="جاري تحميل النظام...")
def load_resources():
    embed_model = SentenceTransformer(EMBEDDING_MODEL)
    db_client = chromadb.PersistentClient(path=DB_DIR)
    collection = db_client.get_or_create_collection(COLLECTION_NAME)
    llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    return embed_model, collection, llm_client


embed_model, collection, llm_client = load_resources()


# ---------------------------------------------------------------------------
# Super admin: organization + admin account management (no chat -- they
# aren't tied to any one organization's documents)
# ---------------------------------------------------------------------------
def render_super_admin_panel():
    st.markdown(
        '<div class="app-hero"><h1>🛠️ لوحة المدير العام</h1>'
        '<p>إدارة المؤسسات وحسابات المديرين</p></div>',
        unsafe_allow_html=True,
    )

    st.subheader("➕ إنشاء مؤسسة جديدة")
    with st.form("create_org_form", clear_on_submit=True):
        new_org_name = st.text_input("اسم المؤسسة")
        if st.form_submit_button("إنشاء المؤسسة"):
            if new_org_name.strip():
                try:
                    auth.create_organization(new_org_name)
                    st.success(f"تم إنشاء المؤسسة: {new_org_name}")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            else:
                st.warning("اكتب اسم المؤسسة أولًا.")

    st.divider()

    st.subheader("➕ إنشاء حساب مدير لمؤسسة")
    orgs = auth.get_organizations()
    if not orgs:
        st.info("لا توجد مؤسسات بعد. أنشئ مؤسسة أولًا.")
    else:
        with st.form("create_admin_form", clear_on_submit=True):
            org_choice = st.selectbox(
                "المؤسسة",
                options=[o["id"] for o in orgs],
                format_func=lambda oid: next(o["name"] for o in orgs if o["id"] == oid),
            )
            new_username = st.text_input("اسم مستخدم المدير")
            new_password = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("إنشاء حساب المدير"):
                if new_username.strip() and new_password:
                    try:
                        auth.create_user(new_username, new_password, "admin", organization_id=org_choice)
                        st.success(f"تم إنشاء حساب المدير '{new_username}' لمؤسسة {next(o['name'] for o in orgs if o['id'] == org_choice)}")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                else:
                    st.warning("املأ اسم المستخدم وكلمة المرور.")

    st.divider()

    st.subheader("📋 المؤسسات والمستخدمون الحاليون")
    all_users = auth.get_all_users()
    for org in orgs:
        org_users = [u for u in all_users if u["organization_id"] == org["id"]]
        with st.expander(f"🏢 {org['name']} ({len(org_users)} مستخدم)"):
            if not org_users:
                st.caption("لا يوجد مستخدمون بعد.")
            for u in org_users:
                role_label = "مدير" if u["role"] == "admin" else "موظف"
                st.write(f"- **{u['username']}** ({role_label})")


# ---------------------------------------------------------------------------
# Admin / Agent: the chat interface, scoped to their organization
# ---------------------------------------------------------------------------
def render_chat_interface():
    org = auth.get_organization(user["organization_id"])
    org_name = org["name"] if org else "—"

    st.markdown(
        f"""
        <div class="app-hero">
            <h1>🤖 المساعد الداخلي لخدمة العملاء</h1>
            <p>{org_name} — اسأل أي سؤال متعلق بإجراءات الشركة أو بيانات العملاء</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    persona_key = st.selectbox(
        "أسلوب الإجابة",
        options=list(PERSONAS.keys()),
        format_func=lambda k: PERSONAS[k]["name"],
        key="persona",
    )

    if user["role"] == "admin":
        with st.expander("📤 إدارة مستندات المؤسسة"):
            uploaded = st.file_uploader("ارفع مستند جديد (txt, pdf, docx)", type=["txt", "pdf", "docx"])
            if uploaded is not None:
                file_bytes = uploaded.getvalue()
                if file_bytes != st.session_state.get("last_uploaded_bytes"):
                    st.session_state.last_uploaded_bytes = file_bytes
                    data_dir = get_org_data_dir(user["organization_id"])
                    save_path = os.path.join(data_dir, uploaded.name)
                    with open(save_path, "wb") as f:
                        f.write(file_bytes)

                    with st.spinner("جاري إضافة الملف..."):
                        result = ingest_single_file(save_path, user["organization_id"], model=embed_model)

                    if result.get("skipped"):
                        st.warning(f"هذا المحتوى موجود بالفعل (كملف '{result['existing_as']}') — لم تتم إضافته مرة أخرى.")
                    else:
                        st.success(f"تمت إضافة {uploaded.name} ({result['chunk_count']} جزء).")
                    st.cache_resource.clear()

            with st.popover("⚠️ إعادة بناء فهرس المؤسسة بالكامل"):
                st.caption("يعيد معالجة كل مستندات هذه المؤسسة فقط — لا يؤثر على أي مؤسسة أخرى.")
                if st.button("🔄 إعادة الفهرسة", type="primary"):
                    with st.spinner("جاري إعادة الفهرسة..."):
                        result = run_ingestion(user["organization_id"], model=embed_model)
                    st.success(f"تم! {result['file_count']} ملف، {result['chunk_count']} جزء.")
                    st.cache_resource.clear()

        with st.expander("👤 إنشاء حساب موظف جديد"):
            with st.form("create_agent_form", clear_on_submit=True):
                new_username = st.text_input("اسم المستخدم")
                new_password = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("إنشاء الحساب"):
                    if new_username.strip() and new_password:
                        try:
                            auth.create_user(new_username, new_password, "agent", organization_id=user["organization_id"])
                            st.success(f"تم إنشاء حساب الموظف '{new_username}'.")
                        except ValueError as e:
                            st.error(str(e))
                    else:
                        st.warning("املأ اسم المستخدم وكلمة المرور.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    def render_message(idx, msg):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] != "assistant":
                return

            sources = msg.get("sources", [])
            if sources:
                tags = "".join(f'<span class="source-tag">📄 {s}</span>' for s in sources)
                st.markdown(
                    f'<div class="source-row"><span class="source-label">المصادر:</span>{tags}</div>',
                    unsafe_allow_html=True,
                )

            if msg.get("audio_path"):
                st.audio(msg["audio_path"])

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
    asked_via_voice = False

    audio_value = st.audio_input("🎤 أو اسأل بصوتك")
    if audio_value is not None:
        audio_bytes = audio_value.getvalue()
        if audio_bytes != st.session_state.get("last_audio_bytes"):
            st.session_state.last_audio_bytes = audio_bytes
            with st.spinner("جاري تحويل الصوت إلى نص..."):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                transcribed = transcribe_audio(tmp_path)
                os.unlink(tmp_path)

            if transcribed:
                question = transcribed
                asked_via_voice = True
            else:
                st.warning("لم أتمكن من فهم الصوت، حاول مرة أخرى.")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        render_message(len(st.session_state.messages) - 1, st.session_state.messages[-1])

        with st.spinner("جاري البحث عن إجابة..."):
            start_time = time.time()

            route = route_question(question, llm_client)

            if route == "sql":
                _, _, _, answer = process_sql_question(question, llm_client)
                sources = []
            else:
                results = retrieve(question, collection, embed_model, user["organization_id"])
                context = build_context(results)
                answer = ask_llm(question, context, llm_client, persona=persona_key)
                sources = sorted({meta["source"] for _, meta, *_ in results})

            latency = time.time() - start_time
            row_id = log_interaction(user["username"], question, answer, sources, latency)

            audio_path = None
            if asked_via_voice:
                os.makedirs(GENERATED_AUDIO_DIR, exist_ok=True)
                audio_path = os.path.join(GENERATED_AUDIO_DIR, f"reply_{row_id}.mp3")
                text_to_speech(answer, audio_path)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "row_id": row_id,
                "feedback": None,
                "audio_path": audio_path,
            }
        )
        render_message(len(st.session_state.messages) - 1, st.session_state.messages[-1])


if user["role"] == "super_admin":
    render_super_admin_panel()
else:
    render_chat_interface()
