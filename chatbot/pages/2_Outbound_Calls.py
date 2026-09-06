"""
Outbound AI follow-up call trigger, ported into the same app/port as the
chatbot -- reuses place_call() from voice-assistant/make_call.py directly.
server.py (Flask) + the cloudflared tunnel must already be running
separately; this page only places the call, it doesn't handle the live
conversation itself.

Login-gated, and the customer list is scoped to the logged-in user's
organization -- an agent only ever sees and calls their own company's
customers, same isolation boundary as the documents.
"""

import os
import sys

import streamlit as st
from dotenv import load_dotenv

from auth_ui import require_login, render_logout_sidebar

VOICE_ASSISTANT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "voice-assistant"))
load_dotenv(os.path.join(VOICE_ASSISTANT_DIR, ".env"))  # Vonage credentials
sys.path.append(VOICE_ASSISTANT_DIR)

from make_call import place_call  # noqa: E402
from crm import lookup_customer, get_customers_by_organization  # noqa: E402

st.set_page_config(page_title="نظام المتابعة الآلي", page_icon="📞", layout="centered")

st.markdown(
    """
    <style>
    .stApp { background: #ffffff; }
    .block-container { max-width: 720px; padding-top: 2rem; direction: rtl; }

    .call-hero {
        background: linear-gradient(120deg, #fb923c 0%, #f97316 60%, #ea580c 100%);
        border-radius: 20px;
        padding: 32px 28px;
        margin-bottom: 22px;
        color: #ffffff;
        text-align: center;
        box-shadow: 0 12px 28px -12px rgba(234, 88, 12, 0.55);
    }
    .call-hero h1 { margin: 0; font-size: 1.7rem; }
    .call-hero p { margin: 8px 0 0; opacity: 0.95; font-size: 0.95rem; }

    .ticket-card {
        background: #fff7ed;
        border: 1px solid #fed7aa;
        border-radius: 14px;
        padding: 16px 18px;
        margin: 14px 0 20px;
    }
    .ticket-card .label { font-size: 0.78rem; color: #9a3412; font-weight: 600; margin-bottom: 4px; }
    .ticket-card .issue { font-size: 1rem; color: #1c1917; }

    div.stButton > button {
        border-radius: 12px;
        font-weight: 700;
        padding: 0.6rem 1.2rem;
        box-shadow: 0 6px 16px -6px rgba(234, 88, 12, 0.5);
    }

    .footnote {
        text-align: center;
        color: #78716c;
        font-size: 0.8rem;
        margin-top: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

user = require_login(allowed_roles=["admin", "agent"])
render_logout_sidebar(user)

st.markdown(
    """
    <div class="call-hero">
        <h1>📞 نظام المتابعة الآلي بالذكاء الاصطناعي</h1>
        <p>مكالمات متابعة تلقائية للتأكد من حل مشاكل العملاء المسجلة في تذاكر الدعم</p>
    </div>
    """,
    unsafe_allow_html=True,
)

org_customers = get_customers_by_organization(user["organization_id"])

if not org_customers:
    st.info("لا يوجد عملاء مسجلون لهذه المؤسسة بعد.")
    st.stop()

to_number = st.selectbox(
    "🗂️ اختر عميلًا",
    options=list(org_customers.keys()),
    format_func=lambda n: f"{org_customers[n]['name']}   ·   {n}   ·   {org_customers[n]['ticket_id']}",
)

customer = lookup_customer(to_number)
if customer:
    st.markdown(
        f"""
        <div class="ticket-card">
            <div class="label">🎫 التذكرة {customer['ticket_id']}</div>
            <div class="issue">{customer['issue']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if st.button("📞  ابدأ المكالمة الآن", type="primary", width="stretch"):
    with st.spinner("جاري الاتصال..."):
        try:
            response = place_call(to_number)
            st.success("تم بدء المكالمة بنجاح ✅")
            st.code(f"Call UUID: {response.uuid}\nStatus: {response.status}")
        except Exception as e:
            st.error(f"فشلت المكالمة: {e}")

st.markdown(
    '<div class="footnote">تأكد أن server.py والـ tunnel شغالين قبل بدء المكالمة</div>',
    unsafe_allow_html=True,
)
