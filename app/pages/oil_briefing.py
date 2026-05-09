"""Oil Impact Briefing — generate a weekly/monthly narrative on diesel-driven
seafood price movements."""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.tools.oil_briefing import generate_oil_briefing
from data.oil_loader import diesel_series


st.title("Oil impact briefing")
st.caption("How recent diesel price moves may be affecting seafood costs.")

st.subheader("Diesel price trend")

oil = diesel_series()
if oil.empty:
    st.warning("No oil price data yet. Run `python data/scripts/oil_scraper.py` to seed.")
else:
    window_label = st.radio(
        "Window",
        ["30 days", "90 days", "180 days", "1 year", "All"],
        horizontal=True,
        index=1,
    )
    window_days = {"30 days": 30, "90 days": 90, "180 days": 180, "1 year": 365}.get(window_label)
    if window_days:
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=window_days)
        oil_w = oil[oil.index >= cutoff]
    else:
        oil_w = oil

    latest = float(oil_w.iloc[-1])
    first = float(oil_w.iloc[0])
    delta = latest - first
    pct = (delta / first * 100) if first else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric("Latest", f"{latest:.2f} THB/L", border=True)
    c2.metric("Change", f"{delta:+.2f} THB/L", f"{pct:+.1f}%", border=True)
    c3.metric("Data points", f"{len(oil_w)}", border=True)

    with st.container(border=True):
        fig = go.Figure(go.Scatter(x=oil_w.index, y=oil_w.values, mode="lines", name="Diesel"))
        fig.update_layout(
            yaxis_title="THB / litre",
            xaxis_title=None,
            height=320,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Generate briefing")

period_label = st.radio(
    "Time range",
    ["Weekly (last 7 days)", "Monthly (last 30 days)"],
    horizontal=True,
)
lang_label = st.radio("Language", ["English", "ไทย"], horizontal=True)

if st.button("Generate briefing", type="primary"):
    period = "weekly" if "Weekly" in period_label else "monthly"
    language = "en" if lang_label == "English" else "th"
    with st.spinner("Generating briefing…"):
        markdown = generate_oil_briefing.invoke({"period": period, "language": language})
    st.session_state["oil_briefing_last"] = {
        "period": period,
        "language": language,
        "markdown": markdown,
    }

last = st.session_state.get("oil_briefing_last")
if last:
    with st.container(border=True):
        st.caption(f"Period: {last['period']} · Language: {last['language']}")
        st.markdown(last["markdown"])
