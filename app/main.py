"""
Seafood Price Comparison Agent — Main Streamlit App

The chat view lives here. Dashboard and Shop Profiles are auto-mounted
from `app/pages/` via Streamlit's multi-page convention.
"""

import streamlit as st

st.set_page_config(
    page_title="Seafood Price Agent",
    page_icon="🐟",
    layout="wide",
)

st.title("Bangkok Seafood Price Advisor 🐟")
st.caption("Ask me about seafood prices, best deals, or build a shopping list.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("e.g. Which shop has cheapest white shrimp today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        st.info("🔧 Agent not yet connected. Run `python -m agent.main` in the terminal to use the CLI version.")
