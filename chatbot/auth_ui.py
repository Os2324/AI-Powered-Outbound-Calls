"""
Shared login screen + role gate, reused at the top of every Streamlit page
(app.py, the dashboard, user management). Centralizing this in one place
means every page enforces login and roles the exact same way.
"""

import streamlit as st

import auth


def require_login(allowed_roles=None):
    """
    Shows a login form if nobody's logged in yet, and blocks the rest of
    the page (via st.stop()) until valid credentials are given. If
    allowed_roles is given and the logged-in user's role isn't in it,
    shows an access-denied message and stops the page instead of
    rendering it.

    Returns the logged-in user dict (id, username, role, organization_id).
    """
    if "user" not in st.session_state:
        st.markdown(
            '<div style="direction: rtl; text-align: center; margin-top: 60px;">'
            "<h2>🔒 تسجيل الدخول</h2></div>",
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("اسم المستخدم")
            password = st.text_input("كلمة المرور", type="password")
            if st.button("دخول", type="primary", width="stretch"):
                user = auth.verify_login(username, password)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")
        st.stop()

    user = st.session_state.user

    if allowed_roles and user["role"] not in allowed_roles:
        st.error("ليس لديك صلاحية للوصول إلى هذه الصفحة.")
        st.stop()

    return user


def render_logout_sidebar(user):
    with st.sidebar:
        st.markdown(f"**{user['username']}**")
        role_labels = {"super_admin": "مدير عام", "admin": "مدير", "agent": "موظف"}
        st.caption(role_labels.get(user["role"], user["role"]))
        if user.get("organization_id"):
            org = auth.get_organization(user["organization_id"])
            if org:
                st.caption(f"🏢 {org['name']}")
        if st.button("🚪 تسجيل الخروج"):
            del st.session_state["user"]
            st.rerun()
