"""Market Insights — oil ↔ seafood correlation explorer."""

from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.loader import load_seafood_data
from data.oil_correlation import MIN_SAMPLE, lag_correlation
from data.oil_loader import diesel_series

LAGS = [0, 7, 14, 21, 28]

st.title("📊 Market Insights — Oil ↔ Seafood")

oil = diesel_series()
seafood_df = load_seafood_data()

if oil.empty:
    st.warning("No oil price data yet. Run `python data/scripts/oil_scraper.py` to seed.")
    st.stop()

if "scrape_date" not in seafood_df.columns or seafood_df["scrape_date"].isna().all():
    st.warning("No historical seafood data yet. Wait for daily scrape to accumulate.")
    st.stop()

species_options = sorted(seafood_df["group_en"].dropna().unique())
species = st.selectbox("Species", species_options)

days = st.slider("Time window (days)", min_value=30, max_value=365, value=90)

# Build seafood daily avg for the selected species
sub = seafood_df.copy()
sub["scrape_date"] = pd.to_datetime(sub["scrape_date"], errors="coerce")
sub = sub[
    (sub["group_en"] == species)
    & sub["price_per_kg"].notna()
    & sub["scrape_date"].notna()
]
if sub.empty:
    st.info(f"No price data available for '{species}'.")
    st.stop()

seafood_series = sub.groupby("scrape_date")["price_per_kg"].mean().sort_index()

# Window
cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
oil_w = oil[oil.index >= cutoff]
seafood_w = seafood_series[seafood_series.index >= cutoff]

# Dual-axis chart
fig = go.Figure()
fig.add_trace(
    go.Scatter(x=seafood_w.index, y=seafood_w.values, name=f"{species} (THB/kg)", yaxis="y1")
)
fig.add_trace(
    go.Scatter(x=oil_w.index, y=oil_w.values, name="Diesel (THB/L)", yaxis="y2")
)
fig.update_layout(
    yaxis=dict(title=f"{species} (THB/kg)"),
    yaxis2=dict(title="Diesel (THB/L)", overlaying="y", side="right"),
    legend=dict(orientation="h"),
    height=420,
)
st.plotly_chart(fig, use_container_width=True)

# Lag correlation
corr = lag_correlation(oil, seafood_series, LAGS)
overlap = pd.concat([oil, seafood_series], axis=1, join="inner").dropna().shape[0]

st.subheader("Lag correlation (Pearson r)")
st.caption(f"Overlap: {overlap} days. Minimum required: {MIN_SAMPLE}.")

if overlap < MIN_SAMPLE:
    st.warning(
        f"Insufficient overlapping data ({overlap} days). "
        f"Need at least {MIN_SAMPLE} days for a meaningful correlation."
    )
else:
    rows = [{"lag (days)": k, "r": v} for k, v in corr.items() if v is not None]
    if rows:
        df = pd.DataFrame(rows).set_index("lag (days)")
        st.dataframe(df.style.format({"r": "{:.3f}"}))
        best_lag, best_r = max(corr.items(), key=lambda kv: (kv[1] or -1))
        st.markdown(
            f"**Takeaway:** {species} prices correlate most strongly with diesel "
            f"~{best_lag} days later (r = {best_r:.2f}, n = {overlap})."
        )

# Limitations
st.subheader("Limitations")
limit_md = (REPO_ROOT / "docs" / "oil-feature-limitations.md")
if limit_md.exists():
    with st.expander("What this view can and can't tell you", expanded=False):
        st.markdown(limit_md.read_text())
