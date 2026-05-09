"""`generate_oil_briefing` tool — cached LLM summary of oil news.

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

from data.oil_loader import load_oil_news

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


def _build_prompt(news: pd.DataFrame, period: str, language: str) -> str:
    lang_label = "Thai (ภาษาไทย)" if language == "th" else "English"
    items = "\n".join(
        f"- [{r.source}] {r.title} ({r.url})\n  {r.snippet}"
        for r in news.itertuples()
    )
    return (
        f"You are an analyst summarizing recent oil/energy news for Thai seafood "
        f"buyers, restaurant owners, and suppliers.\n\n"
        f"Write the briefing in {lang_label}.\n"
        f"Period: last {PERIODS[period]} days.\n\n"
        f"Articles:\n{items}\n\n"
        f"Output rules:\n"
        f"- Maximum 5 bullet points.\n"
        f"- Each bullet must include the source URL inline.\n"
        f"- After bullets, add a short 'Possible seafood cost impact' paragraph.\n"
        f"- Then add a 'Practical actions' section with 2-3 concrete suggestions.\n"
        f"- Avoid unsupported claims; mention uncertainty when data is unclear.\n"
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
    if news is None or news.empty:
        msg = (
            "No recent oil-related news in the selected window."
            if language == "en"
            else "ไม่พบข่าวเกี่ยวกับน้ำมันในช่วงเวลาที่เลือก"
        )
        return msg

    markdown = _summarize_with_llm(_build_prompt(news, period, language))
    _cache_put(period, language, markdown)
    return markdown
