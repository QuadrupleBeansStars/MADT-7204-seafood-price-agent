"""
Seafood Price Comparison Agent — Main Streamlit App

Tabs:
  💬 Chat      — Agentic AI chatbot (agent/main.py)
  📊 Dashboard — Price comparison dashboard (feature/dashboard-page)
  🏪 Shops     — Shop profile explorer (feature/shop-profile-page)
"""

import streamlit as st

st.set_page_config(
    page_title="Seafood Price Agent",
    page_icon="🐟",
    layout="wide",
)

tab_chat, tab_dashboard, tab_shops = st.tabs(["💬 Chat", "📊 Price Dashboard", "🏪 Shop Profiles"])

# ── Tab 1: Chat (agent UI — to be wired in later) ──────────────────────────────
with tab_chat:
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

# ── Tab 2: Price Dashboard (placeholder — Task 4) ──────────────────────────────
with tab_dashboard:
    st.title("📊 Price Dashboard")
    st.info(
        "**This tab is Task 4 — assigned to a team member.**\n\n"
        "The completed feature will show a filterable price table and bar chart "
        "comparing seafood prices across shops, read from `data/raw/seafood_prices_sample.csv`."
    )

# ── Tab 3: Shop Profiles (placeholder — Task 5) ────────────────────────────────
with tab_shops:
    st.title("🏪 Shop Profiles")
    st.info(
        "**This tab is Task 5 — assigned to a team member.**\n\n"
        "The completed feature will show per-shop statistics: items carried, "
        "average price vs market average, and availability rate."
    )
