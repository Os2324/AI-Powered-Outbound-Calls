"""
"First Call Resolutions" report (Phase: Data & Reporting from the PDF).
Reads calls.db and summarizes outcomes -- FCR rate, call completion rate,
average handle time, and the full call log.
"""

import streamlit as st

from db import get_all_calls
from crm import lookup_customer
from make_call import place_call

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

st.markdown(
    '<div class="report-hero"><h1>📊 تقرير حل المشكلات من أول مكالمة (FCR)</h1></div>',
    unsafe_allow_html=True,
)

calls = get_all_calls()

if not calls:
    st.info("لا توجد مكالمات مسجلة بعد. جرب بدء مكالمة من الصفحة الرئيسية أولًا.")
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
