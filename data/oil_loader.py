"""Read helpers for oil_prices.csv and oil_news.csv.

Kept thin so the agent tools and Streamlit pages share one source of truth.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

OIL_PRICES_PATH = Path(__file__).resolve().parent / "raw" / "oil_prices.csv"
OIL_NEWS_PATH = Path(__file__).resolve().parent / "raw" / "oil_news.csv"


def load_oil_prices() -> pd.DataFrame:
    """Return long-form DataFrame: date (datetime), product, thb_per_litre, source."""
    if not OIL_PRICES_PATH.exists():
        return pd.DataFrame(columns=["date", "product", "thb_per_litre", "source"])
    df = pd.read_csv(OIL_PRICES_PATH, parse_dates=["date"])
    return df


def diesel_series() -> pd.Series:
    """Daily diesel price series indexed by date. Picks 'Diesel' product."""
    df = load_oil_prices()
    diesel = df[df["product"].str.casefold() == "diesel"]
    if diesel.empty:
        return pd.Series(dtype=float)
    daily = diesel.groupby("date")["thb_per_litre"].mean().sort_index()
    return daily


def load_oil_news(days: int) -> pd.DataFrame:
    """Return news articles within the last N days."""
    if not OIL_NEWS_PATH.exists():
        return pd.DataFrame(columns=["date", "source", "title", "url", "snippet", "language"])
    df = pd.read_csv(OIL_NEWS_PATH, parse_dates=["date"])
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
    return df[df["date"] >= cutoff].sort_values("date", ascending=False)
