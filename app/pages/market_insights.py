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

st.title("Market insights")
st.caption("Diesel ↔ seafood price correlation explorer.")

oil = diesel_series()
seafood_df = load_seafood_data()

if oil.empty:
    st.warning("No oil price data yet. Run `python data/scripts/oil_scraper.py` to seed.")
    st.stop()

if "scrape_date" not in seafood_df.columns or seafood_df["scrape_date"].isna().all():
    st.warning("No historical seafood data yet. Wait for daily scrape to accumulate.")
    st.stop()

# Restrict species to those that actually have usable price + date data.
seafood_df = seafood_df.copy()
seafood_df["scrape_date"] = pd.to_datetime(seafood_df["scrape_date"], errors="coerce")
valid = seafood_df[
    seafood_df["group_en"].notna()
    & seafood_df["price_per_kg"].notna()
    & seafood_df["scrape_date"].notna()
]
if valid.empty:
    st.warning("No seafood price data available yet.")
    st.stop()

# Build label "English (ไทย)" when a Thai name exists for the group.
th_lookup = (
    valid.dropna(subset=["group_th"])
    .groupby("group_en")["group_th"]
    .agg(lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0])
    .to_dict()
) if "group_th" in valid.columns else {}


def _label(en: str) -> str:
    th = th_lookup.get(en)
    return f"{en} ({th})" if th and th != en else en


species_options = sorted(valid["group_en"].unique())
species = st.selectbox("Species", species_options, format_func=_label)

days = st.slider("Time window (days)", min_value=30, max_value=365, value=90)

sub = valid[valid["group_en"] == species]

seafood_series = sub.groupby("scrape_date")["price_per_kg"].mean().sort_index()

# Window
cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
oil_w = oil[oil.index >= cutoff]
seafood_w = seafood_series[seafood_series.index >= cutoff]

# Dual-axis chart
with st.container(border=True):
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
        margin=dict(l=0, r=0, t=10, b=0),
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
