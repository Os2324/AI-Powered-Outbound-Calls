"""
Web UI for triggering an outbound AI follow-up call.
Reuses place_call() from make_call.py -- this file is just the trigger button
on top of that existing logic. server.py must already be running (handles
the actual conversation once the call connects).
"""

import streamlit as st

from make_call import place_call
from crm import lookup_customer, CUSTOMERS

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

    div[data-testid="stSelectbox"] label { font-weight: 600; }

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

st.markdown(
    """
    <div class="call-hero">
        <h1>📞 نظام المتابعة الآلي بالذكاء الاصطناعي</h1>
        <p>مكالمات متابعة تلقائية للتأكد من حل مشاكل العملاء المسجلة في تذاكر الدعم</p>
    </div>
    """,
    unsafe_allow_html=True,
)

to_number = st.selectbox(
    "🗂️ اختر عميلًا (بيانات CRM تجريبية)",
    options=list(CUSTOMERS.keys()),
    format_func=lambda n: f"{CUSTOMERS[n]['name']}   ·   {n}   ·   {CUSTOMERS[n]['ticket_id']}",
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
