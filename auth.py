"""Login gate. Credentials come from the AUTH_CREDENTIALS_JSON env var, never hardcoded."""
import os
import json
import hashlib
import hmac
import streamlit as st


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()


def _load_users() -> dict:
    raw = os.getenv("AUTH_CREDENTIALS_JSON", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _verify(username: str, password: str, users: dict):
    user = users.get(username)
    if not user:
        return None
    expected = user.get("password_hash", "")
    computed = _hash_password(password, user.get("salt", ""))
    if hmac.compare_digest(expected, computed):
        return user.get("role", "user")
    return None


def require_login():
    """Renders a login form and halts the app until authenticated. Returns (username, role)."""
    if st.session_state.get("authenticated"):
        return st.session_state["username"], st.session_state["role"]

    users = _load_users()

    st.title("Material & Asset Standardization Engine")
    st.markdown("### Sign in to continue")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)

    if submitted:
        if not users:
            st.error("No accounts are configured. Set AUTH_CREDENTIALS_JSON on the server.")
        else:
            role = _verify(username, password, users)
            if role:
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["role"] = role
                st.rerun()
            else:
                st.error("Invalid username or password")

    st.stop()


def logout_button():
    with st.sidebar:
        st.caption(f"Signed in as **{st.session_state.get('username')}** ({st.session_state.get('role')})")
        if st.button("Log out", use_container_width=True):
            for key in ("authenticated", "username", "role"):
                st.session_state.pop(key, None)
            st.rerun()
