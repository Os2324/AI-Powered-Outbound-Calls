"""
"First Call Resolutions" report for outbound calls, ported into the same
app/port as the chatbot. Reads voice-assistant/calls.db and summarizes
outcomes -- FCR rate, call completion rate, average handle time, and the
full call log -- filtered to the logged-in user's organization only.
"""

import os
import sys
import importlib.util

import streamlit as st
from dotenv import load_dotenv

from auth_ui import require_login, render_logout_sidebar

VOICE_ASSISTANT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "voice-assistant"))
load_dotenv(os.path.join(VOICE_ASSISTANT_DIR, ".env"))
sys.path.append(VOICE_ASSISTANT_DIR)

from make_call import place_call  # noqa: E402
from crm import lookup_customer  # noqa: E402


def _load_module(name, path):
    """voice-assistant has its own db.py (calls.db), different from the
    chatbot's own db.py (logs.db) -- load it by explicit path so a plain
    `import db` can't accidentally resolve to the wrong one."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calls_db = _load_module("calls_db", os.path.join(VOICE_ASSISTANT_DIR, "db.py"))
calls_db.init_db()

st.set_page_config(page_title="تقرير المتابعة", page_icon="📊", layout="centered")

st.markdown(
    """
    <style>
    .stApp { background: #ffffff; }
    .block-container { max-width: 780px; padding-top: 2rem; direction: rtl; }

    .report-hero {
        background: linear-gradient(120deg, #fdba74 0%, #f97316 65%, #c2410c 100%);
        border-radius: 20px;
        padding: 28px 26px;
        margin-bottom: 24px;
        color: #ffffff;
        text-align: center;
        box-shadow: 0 12px 28px -12px rgba(194, 65, 12, 0.5);
    }
    .report-hero h1 { margin: 0; font-size: 1.55rem; }

    div[data-testid="stMetric"] {
        background: #fff7ed;
        border: 1px solid #fed7aa;
        border-radius: 14px;
        padding: 12px 14px;
    }

    .followup-row {
        background: #fff7ed;
        border: 1px solid #fed7aa;
        border-radius: 12px;
        padding: 10px 16px;
        margin-bottom: 8px;
    }

    div.stButton > button {
        border-radius: 10px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

user = require_login(allowed_roles=["admin", "agent"])
render_logout_sidebar(user)

st.markdown(
    '<div class="report-hero"><h1>📊 تقرير حل المشكلات من أول مكالمة (FCR)</h1></div>',
    unsafe_allow_html=True,
)

all_calls = calls_db.get_all_calls()

# Scope to this organization only -- a call's org is looked up via the CRM
# record for the number it was made to, since calls.db itself doesn't store
# organization_id directly.
calls = [
    c for c in all_calls
    if (lookup_customer(c["to_number"]) or {}).get("organization_id") == user["organization_id"]
]

if not calls:
    st.info("لا توجد مكالمات مسجلة بعد لهذه المؤسسة. جرب بدء مكالمة من صفحة نظام المتابعة الآلي.")
    st.stop()

total = len(calls)
resolved = sum(1 for c in calls if c["classification"] == "yes")
needs_help = sum(1 for c in calls if c["classification"] == "no")
unsure = sum(1 for c in calls if c["classification"] == "unsure")
questions = sum(1 for c in calls if c["classification"] == "question")

fcr_rate = (resolved / total * 100) if total else 0
completed_without_handoff = resolved + questions
completion_rate = (completed_without_handoff / total * 100) if total else 0

durations = [c["duration_seconds"] for c in calls if c["duration_seconds"]]
avg_duration = sum(durations) / len(durations) if durations else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("إجمالي المكالمات", total)
col2.metric("نسبة الحل من أول مكالمة", f"{fcr_rate:.0f}%")
col3.metric("نسبة الإنجاز بدون تحويل", f"{completion_rate:.0f}%")
col4.metric("متوسط مدة المكالمة", f"{avg_duration:.0f} ث" if avg_duration else "—")

st.progress(
    fcr_rate / 100,
    text=f"✅ مُحلولة: {resolved}   ·   🆘 تحتاج مساعدة: {needs_help}   ·   ❓ غير متأكد: {unsure}   ·   💬 أسئلة: {questions}",
)

needs_followup = [c for c in calls if c["classification"] in ("no", "unsure")]

if needs_followup:
    st.subheader("⚠️ مكالمات تحتاج متابعة")
    for c in needs_followup:
        customer = lookup_customer(c["to_number"]) or {}
        st.markdown('<div class="followup-row">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 3, 2])
        col1.write(f"**{customer.get('name', c['to_number'])}**")
        col2.write(customer.get("issue", "—"))
        if col3.button("🔁 اتصل مرة أخرى", key=f"followup_{c['conversation_uuid']}", width="stretch"):
            with st.spinner("جاري إعادة الاتصال..."):
                try:
                    place_call(c["to_number"])
                    st.success("تم بدء مكالمة متابعة! ✅")
                except Exception as e:
                    st.error(f"فشلت المكالمة: {e}")
        st.markdown("</div>", unsafe_allow_html=True)
    st.divider()

st.subheader("📋 سجل المكالمات")
st.dataframe(
    [
        {
            "الوقت": c["timestamp"],
            "الرقم": c["to_number"],
            "العميل": (lookup_customer(c["to_number"]) or {}).get("name", "—"),
            "التذكرة": (lookup_customer(c["to_number"]) or {}).get("ticket_id", "—"),
            "رد العميل": c["customer_text"],
            "التصنيف": c["classification"],
            "رد الذكاء الاصطناعي": c["reply_text"],
            "المدة (ث)": c["duration_seconds"] or "—",
        }
        for c in calls
    ],
    width="stretch",
)
