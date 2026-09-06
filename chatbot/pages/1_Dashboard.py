"""
Metrics dashboard (Phase 7): reads logs.db and shows usage stats.
Automatically appears as a separate page in the sidebar because it lives
inside the pages/ folder — a Streamlit convention, no extra wiring needed.

Login-gated and scoped to the logged-in user's organization: interactions
are matched back to an organization via the username that asked them
(logs.db itself only stores the username, not organization_id directly).
"""

import streamlit as st

import auth
from auth_ui import require_login, render_logout_sidebar
from db import get_all_interactions

st.set_page_config(page_title="لوحة المتابعة", page_icon="📊", layout="centered")
st.markdown('<div style="direction: rtl; text-align: right;">', unsafe_allow_html=True)

user = require_login(allowed_roles=["admin", "agent"])
render_logout_sidebar(user)

st.title("📊 لوحة متابعة المساعد الداخلي")

username_to_org = {u["username"]: u["organization_id"] for u in auth.get_all_users()}

all_rows = get_all_interactions()
rows = [r for r in all_rows if username_to_org.get(r["agent_name"]) == user["organization_id"]]

if not rows:
    st.info("لا توجد بيانات مسجلة بعد لهذه المؤسسة. جرب طرح سؤال في صفحة المحادثة أولًا.")
    st.stop()

total = len(rows)
avg_latency = sum(r["latency_seconds"] or 0 for r in rows) / total
up_count = sum(1 for r in rows if r["feedback"] == "up")
down_count = sum(1 for r in rows if r["feedback"] == "down")
no_feedback = total - up_count - down_count

col1, col2, col3, col4 = st.columns(4)
col1.metric("إجمالي الأسئلة", total)
col2.metric("متوسط زمن الإجابة", f"{avg_latency:.1f} ث")
col3.metric("تقييمات إيجابية 👍", up_count)
col4.metric("تقييمات سلبية 👎", down_count)

if up_count + down_count > 0:
    satisfaction = up_count / (up_count + down_count) * 100
    st.progress(satisfaction / 100, text=f"نسبة الرضا: {satisfaction:.0f}% (من أصل {up_count + down_count} تقييم، بدون احتساب {no_feedback} سؤال بلا تقييم)")

st.subheader("سجل الأسئلة والإجابات")
st.dataframe(
    [
        {
            "الوقت": r["timestamp"],
            "الاسم": r["agent_name"],
            "السؤال": r["question"],
            "المصادر": r["sources"],
            "الزمن (ث)": round(r["latency_seconds"] or 0, 2),
            "التقييم": {"up": "👍", "down": "👎", None: "—"}[r["feedback"]],
        }
        for r in rows
    ],
    width="stretch",
)

st.markdown("</div>", unsafe_allow_html=True)
