"""Login gate. Credentials come from the AUTH_CREDENTIALS_JSON env var, never hardcoded."""
import os
import json
import time
import base64
import hashlib
import hmac
import streamlit as st

SESSION_TTL_SECONDS = 12 * 3600
_SECRET = os.getenv("AUTH_SECRET_KEY", "")


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


def _sign(payload: str) -> str:
    return hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _make_session_token(username: str, role: str) -> str:
    expiry = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{username}|{role}|{expiry}"
    token = f"{payload}|{_sign(payload)}"
    return base64.urlsafe_b64encode(token.encode()).decode()


def _parse_session_token(token: str):
    try:
        username, role, expiry, sig = base64.urlsafe_b64decode(token.encode()).decode().split("|")
        payload = f"{username}|{role}|{expiry}"
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        if int(expiry) < time.time():
            return None
        return username, role
    except Exception:
        return None


_LOGIN_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 50% 0%, #1f2a44 0%, #0b1120 60%);
}
[data-testid="stHeader"] { background: transparent; }

.st-key-login_card {
    max-width: 400px;
    margin: 6vh auto 0 auto;
    padding: 2.5rem 2.25rem 2rem 2.25rem;
    background: rgba(255, 255, 255, 0.97);
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
}
.login-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 14px;
    background: linear-gradient(135deg, #f97362, #dc4c3e);
    font-size: 28px;
    margin: 0 auto 1rem auto;
}
.login-title {
    text-align: center;
    font-size: 1.35rem;
    font-weight: 700;
    color: #101828;
    margin-bottom: 0.15rem;
}
.login-subtitle {
    text-align: center;
    font-size: 0.9rem;
    color: #667085;
    margin-bottom: 1.75rem;
}
.st-key-login_card div[data-testid="stForm"] {
    border: none;
    padding: 0;
}
.login-footer {
    text-align: center;
    font-size: 0.75rem;
    color: #98a2b3;
    margin-top: 1.25rem;
}
</style>
"""


def require_login():
    """Renders a login form and halts the app until authenticated. Returns (username, role)."""
    if not st.session_state.get("authenticated") and _SECRET:
        token = st.query_params.get("s")
        if token:
            parsed = _parse_session_token(token)
            if parsed:
                st.session_state["authenticated"] = True
                st.session_state["username"], st.session_state["role"] = parsed

    if st.session_state.get("authenticated"):
        return st.session_state["username"], st.session_state["role"]

    users = _load_users()

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        with st.container(key="login_card"):
            st.markdown('<div class="login-icon">🏗️</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-title">Material &amp; Asset Standardization</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-subtitle">Sign in to continue</div>', unsafe_allow_html=True)

            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
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
                        if _SECRET:
                            st.query_params["s"] = _make_session_token(username, role)
                        st.rerun()
                    else:
                        st.error("Invalid username or password")

            st.markdown('<div class="login-footer">Churchgate Group</div>', unsafe_allow_html=True)

    st.stop()


def logout_button():
    with st.sidebar:
        st.caption(f"Signed in as **{st.session_state.get('username')}** ({st.session_state.get('role')})")
        if st.button("Log out", use_container_width=True):
            for key in ("authenticated", "username", "role"):
                st.session_state.pop(key, None)
            st.query_params.pop("s", None)
            st.rerun()
