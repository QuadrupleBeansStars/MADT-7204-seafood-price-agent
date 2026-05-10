"""Tests for agent/tools/seafood_prices.py.

The headline regression test (test_dedupe_collapses_history_to_latest)
guards against a real production bug: query_seafood_prices and
get_best_deals returned every historical scrape row, so the same shop +
item + option appeared N times (once per scrape day). The agent then
rendered N consecutive rows of the same shop as if they were N different
offers. The fix is _latest_per_shop_item.
"""
from __future__ import annotations

import pandas as pd
import pytest

from agent.tools import seafood_prices as mod
from agent.tools.seafood_prices import (
    _latest_per_shop_item,
    get_best_deals,
    query_seafood_prices,
)


def _make_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    # Ensure schema columns the tools expect exist.
    for col in [
        "source", "group_en", "group_th", "option", "scrape_date",
        "item_name_website", "category", "category_th",
        "price_per_kg", "selling_price", "weight_kg", "link",
    ]:
        if col not in df.columns:
            df[col] = None
    return df


@pytest.fixture
def history_with_duplicates(monkeypatch):
    """20 daily snapshots of the same shop+item+option + a second shop's
    latest snapshot. Mirrors the production bug shape."""
    rows = []
    base_date = pd.Timestamp("2026-04-20")
    for i in range(20):
        rows.append({
            "scrape_date": (base_date + pd.Timedelta(days=i)).date().isoformat(),
            "source": "PakPanang Direct",
            "group_en": "Tiger Prawn",
            "group_th": "กุ้งลายเสือ",
            "option": "31-35 ตัวโล",
            "price_per_kg": 400 + i,  # day-by-day variation
            "selling_price": 400 + i,
            "weight_kg": 1.0,
            "category": "shrimp",
            "category_th": "กุ้ง",
            "item_name_website": "กุ้งลายเสือ",
            "link": "https://example/pakpanang",
        })
    # Two other shops with much higher current prices, so PakPanang's 419
    # ends up well below the cross-shop average and shows up in best_deals.
    for shop, price, slug in (
        ("Cha-Am Seafood", 700, "cham"),
        ("Gulf Fresh Co.", 750, "gulf"),
    ):
        rows.append({
            "scrape_date": "2026-05-09",
            "source": shop,
            "group_en": "Tiger Prawn",
            "group_th": "กุ้งลายเสือ",
            "option": "31-35 ตัวโล",
            "price_per_kg": float(price),
            "selling_price": float(price),
            "weight_kg": 1.0,
            "category": "shrimp",
            "category_th": "กุ้ง",
            "item_name_website": "กุ้งลายเสือ",
            "link": f"https://example/{slug}",
        })
    df = _make_df(rows)
    monkeypatch.setattr(mod, "load_seafood_data", lambda: df)
    return df


def test_dedupe_collapses_history_to_latest(history_with_duplicates):
    """Regression: 20 historical rows of one shop+item+option must collapse to 1."""
    out = _latest_per_shop_item(history_with_duplicates)
    pak = out[(out["source"] == "PakPanang Direct") & (out["group_en"] == "Tiger Prawn")]
    assert len(pak) == 1, "expected exactly one row after dedup"
    # The kept row must be the latest snapshot (price 400+19 = 419 in this fixture)
    assert pak.iloc[0]["price_per_kg"] == 419
    assert pak.iloc[0]["scrape_date"] == "2026-05-09"


def test_query_seafood_prices_returns_one_row_per_shop_item(history_with_duplicates):
    out = query_seafood_prices.invoke({"item": "Tiger Prawn"})
    # Should mention each shop exactly once
    assert out.count("PakPanang Direct") == 1
    assert out.count("Cha-Am Seafood") == 1
    assert out.count("Gulf Fresh Co.") == 1


def test_get_best_deals_uses_current_prices_only(history_with_duplicates):
    out = get_best_deals.invoke({"category": "shrimp"})
    # PakPanang's current price is 419; the historical 400-418 should be gone
    assert "419" in out
    assert "400" not in out  # earliest historical price must not appear


def test_dedup_keeps_rows_without_scrape_date():
    """Registry fallback rows have no scrape_date; they should pass through."""
    df = _make_df([
        {"source": "S", "group_en": "X", "option": "-", "scrape_date": None, "price_per_kg": 100},
        {"source": "S", "group_en": "X", "option": "-", "scrape_date": "2026-05-09", "price_per_kg": 200},
    ])
    out = _latest_per_shop_item(df)
    # Same shop+item+option: dated row wins
    assert len(out) == 1
    assert out.iloc[0]["price_per_kg"] == 200


def test_empty_input_handled():
    assert _latest_per_shop_item(pd.DataFrame()).empty
