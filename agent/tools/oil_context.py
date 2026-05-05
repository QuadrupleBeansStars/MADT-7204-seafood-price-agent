"""`get_oil_context` agent tool + `oil_snapshot_line` helper for system prompt.

The tool returns current diesel price, recent percent changes, and (when a
species is given and there is enough overlap) lagged correlation with the
species' average price.
"""

from __future__ import annotations

import pandas as pd
from langchain_core.tools import tool

from data.loader import load_seafood_data
from data.oil_correlation import MIN_SAMPLE, lag_correlation, pct_change
from data.oil_loader import diesel_series

LAGS = [0, 7, 14, 21, 28]


def _seafood_daily_avg(species: str) -> pd.Series:
    """Daily mean price-per-kg for a species (matched against group_en)."""
    df = load_seafood_data()
    if "scrape_date" not in df.columns:
        return pd.Series(dtype=float)
    mask = df["group_en"].str.contains(species, case=False, na=False) | df[
        "group_th"
    ].str.contains(species, case=False, na=False)
    sub = df[mask & df["price_per_kg"].notna()].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    sub["scrape_date"] = pd.to_datetime(sub["scrape_date"], errors="coerce")
    sub = sub.dropna(subset=["scrape_date"])
    return sub.groupby("scrape_date")["price_per_kg"].mean().sort_index()


def oil_snapshot_line() -> str:
    """One-line snapshot for system prompt injection. Empty string if no data."""
    s = diesel_series()
    if s.empty:
        return ""
    latest = s.iloc[-1]
    c7 = pct_change(s, 7)
    c30 = pct_change(s, 30)
    parts = [f"Diesel {latest:.2f} THB/L"]
    if c7 is not None:
        parts.append(f"{c7:+.1f}% 7d")
    if c30 is not None:
        parts.append(f"{c30:+.1f}% 30d")
    return f"Current oil context: {parts[0]} (" + ", ".join(parts[1:]) + ")."


@tool
def get_oil_context(species: str | None = None) -> dict:
    """Return current Thai diesel price, recent change, and (if species given)
    lagged correlation with that species' avg price.

    Use this whenever the user asks why prices may move, or when answering
    about a specific species and oil moves are large enough to be relevant.

    Args:
        species: Optional seafood species (English or Thai partial match).
                 When provided and enough overlapping data exists (>= 30 days),
                 the response includes Pearson r at lags 0/7/14/21/28 days.
    """
    s = diesel_series()
    out: dict = {
        "diesel_thb_per_l": float(s.iloc[-1]) if not s.empty else None,
        "change_7d_pct": pct_change(s, 7),
        "change_30d_pct": pct_change(s, 30),
        "lag_correlation": None,
        "n_days_overlap": 0,
    }
    if species:
        seafood = _seafood_daily_avg(species)
        joined = pd.concat([s, seafood], axis=1, join="inner").dropna()
        out["n_days_overlap"] = int(len(joined))
        if len(joined) >= MIN_SAMPLE:
            corr = lag_correlation(s, seafood, LAGS)
            out["lag_correlation"] = {str(k): v for k, v in corr.items()}
    return out
