"""
Seafood Price Comparison Agent — Streamlit entry point.

This is the orchestrator: it handles env/secrets, the login gate, defines
the multi-page navigation, renders the shared sidebar, and dispatches
to the selected page.

Run with: streamlit run app/main.py
"""

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Make the repo root importable so pages can reach `agent.*`.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auth import require_login

st.set_page_config(
    page_title="Seafood Price Agent",
    page_icon="🐟",
    layout="wide",
)

load_dotenv()

# Bridge Streamlit secrets → env so downstream code (agent/main.py,
# Langfuse) reads them identically whether running on Streamlit Cloud
# (secrets.toml / dashboard UI) or local dev (.env). Env wins if set.
_BRIDGED_SECRETS = (
    "ANTHROPIC_API_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_HOST",
)
try:
    for _key in _BRIDGED_SECRETS:
        if not os.getenv(_key):
            _val = st.secrets.get(_key)
            if _val:
                os.environ[_key] = _val
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    pass

require_login()


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🐟 Seafood Price Advisor")
        st.caption("Your AI guide to Bangkok seafood markets.")
        st.markdown(
            '<span style="background:#E0E7FF;color:#1E3A8A;padding:2px 8px;'
            'border-radius:12px;font-size:0.8rem;">'
            "Powered by Claude Sonnet 4.5</span>",
            unsafe_allow_html=True,
        )
        st.divider()

        if st.button("🧹 Clear chat history", use_container_width=True):
            st.session_state.pop("messages", None)
            st.session_state.pop("last_error", None)
            st.toast("Chat history cleared.", icon="🧹")
            st.rerun()

        st.markdown(
            "📖 [Usage guide](https://github.com/QuadrupleBeansStars/"
            "MADT-7204-seafood-price-agent/blob/main/docs/chatbot_usage.md)"
        )

        st.divider()
        if st.button("Log out", use_container_width=True):
            st.session_state.clear()
            st.rerun()


chat_page = st.Page(
    "pages/chat.py",
    title="Chat",
    icon="💬",
    default=True,
)
dashboard_page = st.Page(
    "pages/dashboard.py",
    title="Dashboard",
    icon="📊",
)
shop_page = st.Page(
    "pages/shop_profile.py",
    title="Shop Profile",
    icon="🏪",
)

nav = st.navigation([chat_page, dashboard_page, shop_page])
_render_sidebar()
nav.run()
