"""`generate_oil_briefing` tool — cached LLM summary of oil price moves +
related news.

Inputs always include diesel price context (level + 7/30d change) and the
top-moving seafood species over the period. News is included when the
scraper has matching items; the briefing still produces useful output on
days with no oil-specific news.

Cache: SQLite, keyed by (period, language), 6h TTL, also invalidated when
the news scraper writes a fresh sentinel file.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pandas as pd
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from data.loader import load_seafood_data
from data.oil_correlation import pct_change
from data.oil_loader import diesel_series, load_oil_news

CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "briefing_cache.sqlite"
SENTINEL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / ".oil_news_sentinel"
TTL_SECONDS = 6 * 3600
PERIODS = {"weekly": 7, "monthly": 30}


def _init_cache(path: Path | None = None) -> None:
    p = path or CACHE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS briefings ("
            "  period TEXT NOT NULL, language TEXT NOT NULL,"
            "  generated_at REAL NOT NULL, markdown TEXT NOT NULL,"
            "  PRIMARY KEY (period, language))"
        )


def _sentinel_mtime() -> float:
    return SENTINEL_PATH.stat().st_mtime if SENTINEL_PATH.exists() else 0.0


def _cache_get(period: str, language: str) -> str | None:
    _init_cache()
    with sqlite3.connect(CACHE_PATH) as conn:
        row = conn.execute(
            "SELECT generated_at, markdown FROM briefings WHERE period=? AND language=?",
            (period, language),
        ).fetchone()
    if row is None:
        return None
    generated_at, markdown = row
    if time.time() - generated_at > TTL_SECONDS:
        return None
    if generated_at < _sentinel_mtime():
        return None
    return markdown


def _cache_put(period: str, language: str, markdown: str) -> None:
    _init_cache()
    with sqlite3.connect(CACHE_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO briefings(period, language, generated_at, markdown)"
            " VALUES (?, ?, ?, ?)",
            (period, language, time.time(), markdown),
        )


def _diesel_block() -> str:
    """One-paragraph diesel summary: level + recent percent changes."""
    s = diesel_series()
    if s.empty:
        return "Diesel price data: unavailable."
    latest = s.iloc[-1]
    parts = [f"latest {latest:.2f} THB/L (as of {s.index.max().date()})"]
    for d, label in ((7, "7d"), (30, "30d"), (90, "90d")):
        c = pct_change(s, d)
        if c is not None:
            parts.append(f"{c:+.1f}% {label}")
    return "Diesel price: " + ", ".join(parts) + "."


def _top_movers_block(days: int) -> str:
    """Top-moving seafood species (by mean price-per-kg) over the window."""
    df = load_seafood_data()
    if "scrape_date" not in df.columns:
        return "Seafood price moves: insufficient history."
    df = df[df["price_per_kg"].notna() & df["group_en"].notna()].copy()
    df["scrape_date"] = pd.to_datetime(df["scrape_date"], errors="coerce")
    df = df.dropna(subset=["scrape_date"])
    if df.empty:
        return "Seafood price moves: insufficient history."
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
    earlier_cutoff = cutoff - pd.Timedelta(days=days)
    recent = df[df["scrape_date"] >= cutoff]
    prior = df[(df["scrape_date"] >= earlier_cutoff) & (df["scrape_date"] < cutoff)]
    if recent.empty or prior.empty:
        return "Seafood price moves: not enough overlapping snapshots."
    a = recent.groupby("group_en")["price_per_kg"].mean()
    b = prior.groupby("group_en")["price_per_kg"].mean()
    common = a.index.intersection(b.index)
    if len(common) == 0:
        return "Seafood price moves: no species present in both periods."
    pct = ((a[common] - b[common]) / b[common] * 100).sort_values()
    bottom = pct.head(3)
    top = pct.tail(3)[::-1]
    lines = ["Seafood price moves vs. prior window:"]
    for name, v in top.items():
        lines.append(f"  - {name}: {v:+.1f}%")
    if len(common) >= 6:
        lines.append("  …")
        for name, v in bottom.items():
            lines.append(f"  - {name}: {v:+.1f}%")
    return "\n".join(lines)


def _build_prompt(news: pd.DataFrame, period: str, language: str) -> str:
    lang_label = "Thai (ภาษาไทย)" if language == "th" else "English"
    days = PERIODS[period]

    if news is None or news.empty:
        news_block = "Recent oil-specific news: none in the window."
    else:
        items = "\n".join(
            f"- [{r.source}] {r.title} ({r.url})\n  {r.snippet}"
            for r in news.itertuples()
        )
        news_block = f"Recent oil-specific news:\n{items}"

    return (
        f"You are an analyst writing a short briefing for Thai seafood buyers, "
        f"restaurant owners, and suppliers on how recent diesel/oil moves may "
        f"affect their costs.\n\n"
        f"Write the briefing in {lang_label}.\n"
        f"Period: last {days} days.\n\n"
        f"{_diesel_block()}\n\n"
        f"{_top_movers_block(days)}\n\n"
        f"{news_block}\n\n"
        f"Output rules:\n"
        f"- Lead with a 1-sentence headline summarising the diesel move.\n"
        f"- Up to 5 bullets covering: diesel level, biggest seafood movers, "
        f"and any news (cite URL inline when present).\n"
        f"- Add a short 'Possible seafood cost impact' paragraph linking the "
        f"diesel move to the species above where plausible.\n"
        f"- Add a 'Practical actions' section with 2-3 concrete suggestions.\n"
        f"- Avoid unsupported claims; flag uncertainty when data is thin.\n"
        f"- Use simple business language.\n"
    )


def _summarize_with_llm(prompt: str) -> str:
    """Call Claude. Patched in tests."""
    llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0)
    return llm.invoke([HumanMessage(content=prompt)]).content


@tool
def generate_oil_briefing(period: str, language: str) -> str:
    """Generate (or fetch from cache) a briefing of recent oil/energy news
    that may affect Thai seafood costs.

    Args:
        period: 'weekly' (last 7 days) or 'monthly' (last 30 days).
        language: 'th' or 'en'.
    """
    if period not in PERIODS:
        raise ValueError(f"period must be 'weekly' or 'monthly', got {period!r}")
    if language not in ("th", "en"):
        raise ValueError(f"language must be 'th' or 'en', got {language!r}")

    cached = _cache_get(period, language)
    if cached is not None:
        return cached

    news = load_oil_news(days=PERIODS[period])
    markdown = _summarize_with_llm(_build_prompt(news, period, language))
    _cache_put(period, language, markdown)
    return markdown
