"""Shared login gate for the Streamlit app.

One team-wide password, checked against st.secrets["app_password"] with
APP_PASSWORD env fallback for local dev. The orchestrator (app/main.py)
calls this once as the single auth gate for every page; the sidebar
Log out button also lives in the orchestrator.
"""

import os

import streamlit as st


def _expected_password() -> str | None:
    try:
        pw = st.secrets.get("app_password")
        if pw:
            return pw
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        pass
    return os.getenv("APP_PASSWORD")


def require_login() -> None:
    if st.session_state.get("authenticated"):
        return

    expected = _expected_password()
    if not expected:
        st.error(
            "No app password configured. Set `app_password` in "
            "`.streamlit/secrets.toml` or the `APP_PASSWORD` env var."
        )
        st.stop()

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("# 🐟 Seafood Price Advisor")
        st.caption(
            "Your AI guide to Bangkok seafood markets. "
            "Sign in with the team password to continue."
        )

        with st.form("login_form"):
            pw = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            if pw == expected:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")

    st.stop()
