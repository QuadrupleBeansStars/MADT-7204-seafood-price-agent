"""Tests for data/loader.py — focuses on the dedupe helper that the
dashboard, shop_profile, and agent tools all depend on."""
from __future__ import annotations

import pandas as pd

from data.loader import _prepare_scraped, latest_per_shop_item


def _make_df(rows):
    df = pd.DataFrame(rows)
    for col in ("source", "group_en", "option", "scrape_date", "price_per_kg"):
        if col not in df.columns:
            df[col] = None
    return df


def test_latest_per_shop_item_dedupes_history():
    """Regression for dashboard ฿15k/kg bars: 15 days of the same
    shop+item+option must collapse to 1 row at the latest date."""
    rows = []
    for i in range(15):
        rows.append({
            "source": "PakPanang Direct",
            "group_en": "Banana Prawn",
            "option": "31-35 ตัวโล",
            "scrape_date": (pd.Timestamp("2026-04-25") + pd.Timedelta(days=i)).date().isoformat(),
            "price_per_kg": 400 + i,
        })
    df = _make_df(rows)
    out = latest_per_shop_item(df)
    assert len(out) == 1
    assert out.iloc[0]["price_per_kg"] == 414
    assert out.iloc[0]["scrape_date"] == "2026-05-09"


def test_latest_per_shop_item_keeps_distinct_options():
    """Different size options for the same shop+species must NOT collapse."""
    df = _make_df([
        {"source": "S", "group_en": "Tiger Prawn", "option": "31-35 ตัวโล",
         "scrape_date": "2026-05-11", "price_per_kg": 400},
        {"source": "S", "group_en": "Tiger Prawn", "option": "26-30 ตัวโล",
         "scrape_date": "2026-05-11", "price_per_kg": 450},
    ])
    out = latest_per_shop_item(df)
    assert len(out) == 2


def test_latest_per_shop_item_handles_empty_input():
    assert latest_per_shop_item(pd.DataFrame()).empty


# ── Pack-only rows are dropped ───────────────────────────────────────────────


def test_prepare_scraped_drops_pack_only_rows():
    """Rows with no per-kg price (pack-only items the weight parser cannot
    resolve) must not reach the UI/agent — the biz team found them
    confusing since they can't be compared apples-to-apples. Rows whose
    weight IS encoded in the option text are kept (per-kg is computed)."""
    scraped = pd.DataFrame([
        # Already per-kg — kept
        {"source": "S", "group_en": "Squid", "group_th": "หมึก",
         "option": "L", "weight_kg": None, "selling_price": 400.0,
         "price_per_kg": 400.0, "link": ""},
        # Weight in option text → per-kg computed → kept
        {"source": "S", "group_en": "Squid", "group_th": "หมึก",
         "option": "500 กรัม", "weight_kg": None, "selling_price": 250.0,
         "price_per_kg": None, "link": ""},
        # Pure piece count, no weight signal → no per-kg → dropped
        {"source": "S", "group_en": "Crab Meat", "group_th": "เนื้อปู",
         "option": "3 ชิ้น/แพ็ค", "weight_kg": None, "selling_price": 380.0,
         "price_per_kg": None, "link": ""},
    ])
    out = _prepare_scraped(scraped)
    assert len(out) == 2
    assert out["price_per_kg"].notna().all()
    assert "Crab Meat" not in out["group_en"].values
