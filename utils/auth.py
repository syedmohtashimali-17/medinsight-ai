"""Simple demo-grade login gate (no database).

Usage in app.py (right after st.set_page_config):
    from utils.auth import require_login, logout_button
    require_login()        # stops the page here until the user logs in
    logout_button()        # optional: shows 'Logged in as X' + Logout in the sidebar

Where users come from (first match wins):
  1. Streamlit secrets:   [users]  alice = "plain-or-sha256:<hex>"
  2. Env var AUTH_USERS:  "alice:pass1,bob:pass2"
  3. Fallback demo account: demo / medinsight123   (hint is shown on the login screen)
Set AUTH_DISABLED=1 to skip login (local development).

Passwords in secrets may be plain text or 'sha256:<hexdigest>'.
This is a demo gate, not production security: accounts are not stored anywhere
and nothing is remembered after a refresh.
"""
import hashlib
import hmac
import os
from pathlib import Path

import streamlit as st

DEMO_USER, DEMO_PASS = "demo", "medinsight123"


def _secrets_file_exists() -> bool:
    # Touching st.secrets without a secrets.toml makes Streamlit draw a red error box,
    # so check for the file first.
    return any(p.is_file() for p in (Path.home() / ".streamlit" / "secrets.toml",
                                     Path.cwd() / ".streamlit" / "secrets.toml"))


def _load_users() -> dict:
    users = {}
    if _secrets_file_exists():
        try:
            if "users" in st.secrets:
                users.update({str(k): str(v) for k, v in st.secrets["users"].items()})
        except Exception:
            pass
    raw = os.getenv("AUTH_USERS", "")
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        if ":" in pair:
            name, pw = pair.split(":", 1)
            users[name.strip()] = pw.strip()
    return users


def _check(stored: str, given: str) -> bool:
    if stored.startswith("sha256:"):
        digest = hashlib.sha256(given.encode()).hexdigest()
        return hmac.compare_digest(stored[7:].lower(), digest)
    return hmac.compare_digest(stored.encode(), given.encode())


def verify(username: str, password: str, users: dict) -> bool:
    stored = users.get((username or "").strip())
    return stored is not None and _check(stored, password or "")


def require_login():
    """Call once near the top of app.py. Renders the login form and st.stop()s until logged in."""
    if os.getenv("AUTH_DISABLED", "").lower() in ("1", "true", "yes"):
        st.session_state.setdefault("auth_user", "dev")
        return
    if st.session_state.get("auth_user"):
        return

    users = _load_users()
    using_fallback = not users
    if using_fallback:
        users = {DEMO_USER: DEMO_PASS}

    st.title("MedInsight AI")
    st.subheader("Log in")
    with st.container(border=True):
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Log in", type="primary"):
            if verify(username, password, users):
                st.session_state["auth_user"] = username.strip()
                st.rerun()
            else:
                st.error("Incorrect username or password.")
    if using_fallback:
        st.caption(f"Demo account: username `{DEMO_USER}`, password `{DEMO_PASS}`")
    st.caption("This tool helps explain laboratory information and does not replace "
               "professional medical advice or diagnosis.")
    st.stop()


def logout_button():
    """Sidebar: shows the current user and a Logout button (clears all session data)."""
    user = st.session_state.get("auth_user")
    if not user:
        return
    with st.sidebar:
        st.caption(f"Logged in as **{user}**")
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()
