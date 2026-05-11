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
    _resolve_best_match,
    get_best_deals,
    get_purchase_quote,
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


def test_get_best_deals_uses_current_prices_only(history_with_duplicates, monkeypatch):
    # New get_best_deals requires a Talaad Thai benchmark (no floating average).
    # Mock one well above the cheapest current price so PakPanang shows as a deal.
    bench_df = pd.DataFrame([{
        "group_en": "Tiger Prawn",
        "group_th": "กุ้งลายเสือ",
        "price_per_kg": 800.0,
        "price_min": 800.0,
        "price_max": 800.0,
        "n_variants": 1,
        "snapshot_date": pd.Timestamp("2026-05-09"),
        "link": "",
    }])
    monkeypatch.setattr(mod, "load_talaadthai_benchmark", lambda: bench_df)

    out = get_best_deals.invoke({"category": "shrimp"})
    # PakPanang's current price is 419; historical 400-418 must be gone.
    assert "419" in out
    # Earliest historical day-0 price (400) must not appear as PakPanang's price.
    # (It can still appear as e.g. a benchmark digit, so check it's not in a price slot.)
    assert "400/kg" not in out


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


# ── Best-Match resolution (A1) ───────────────────────────────────────────────


@pytest.fixture
def two_shrimp_species(monkeypatch):
    """A generic 'shrimp' query matches both Tiger Prawn and White Shrimp.
    White Shrimp has more shops (3) and a benchmark → must win Best-Match."""
    rows = [
        # Tiger Prawn — 1 shop, no benchmark
        {"source": "Shop A", "group_en": "Tiger Prawn", "group_th": "กุ้งลายเสือ",
         "category": "shrimp", "category_th": "กุ้ง", "option": "-",
         "scrape_date": "2026-05-09", "price_per_kg": 400.0, "selling_price": 400.0,
         "weight_kg": 1.0, "item_name_website": "tiger", "link": ""},
        # White Shrimp (Vannamei) — 3 shops, benchmark exists
        {"source": "Shop A", "group_en": "Vannamei Shrimp", "group_th": "กุ้งขาว",
         "category": "shrimp", "category_th": "กุ้ง", "option": "L",
         "scrape_date": "2026-05-09", "price_per_kg": 250.0, "selling_price": 250.0,
         "weight_kg": 1.0, "item_name_website": "vannamei", "link": ""},
        {"source": "Shop B", "group_en": "Vannamei Shrimp", "group_th": "กุ้งขาว",
         "category": "shrimp", "category_th": "กุ้ง", "option": "L",
         "scrape_date": "2026-05-09", "price_per_kg": 260.0, "selling_price": 260.0,
         "weight_kg": 1.0, "item_name_website": "vannamei", "link": ""},
        {"source": "Shop C", "group_en": "Vannamei Shrimp", "group_th": "กุ้งขาว",
         "category": "shrimp", "category_th": "กุ้ง", "option": "L",
         "scrape_date": "2026-05-09", "price_per_kg": 240.0, "selling_price": 240.0,
         "weight_kg": 1.0, "item_name_website": "vannamei", "link": ""},
    ]
    df = _make_df(rows)
    monkeypatch.setattr(mod, "load_seafood_data", lambda: df)
    bench_df = pd.DataFrame([{
        "group_en": "Vannamei Shrimp", "group_th": "กุ้งขาว",
        "price_per_kg": 300.0, "price_min": 300.0, "price_max": 300.0,
        "n_variants": 1, "snapshot_date": pd.Timestamp("2026-05-09"), "link": "",
    }])
    monkeypatch.setattr(mod, "load_talaadthai_benchmark", lambda: bench_df)
    return df


def test_best_match_picks_high_liquidity_with_benchmark(two_shrimp_species):
    out, note = _resolve_best_match(two_shrimp_species, "กุ้ง")
    assert set(out["group_en"].unique()) == {"Vannamei Shrimp"}
    assert note is not None and "Vannamei Shrimp" in note


def test_query_seafood_prices_resolves_generic_term(two_shrimp_species):
    out = query_seafood_prices.invoke({"item": "กุ้ง"})
    # Should surface the Best-Match note + only Vannamei prices
    assert "กุ้งขาว" in out
    # Tiger Prawn's shelf price (฿400) must not appear as a listed offer.
    assert "฿400/kg" not in out
    assert "กุ้งลายเสือ" not in out  # Thai name only appears in row listings


def test_best_match_passes_through_when_only_one_species():
    rows = [
        {"source": "S", "group_en": "Salmon", "group_th": "ปลาแซลมอน",
         "category": "fish", "category_th": "ปลา", "option": "-",
         "scrape_date": "2026-05-09", "price_per_kg": 500.0, "selling_price": 500.0,
         "weight_kg": 1.0, "item_name_website": "salmon", "link": ""},
    ]
    df = _make_df(rows)
    out, note = _resolve_best_match(df, "salmon")
    assert len(out) == 1
    assert note is None


# ── Pro-forma quote (A4) ─────────────────────────────────────────────────────


def test_purchase_quote_picks_lowest_landed_cost(monkeypatch):
    rows = [
        # Cheap shelf price but no free-delivery threshold (PakPanang per_kg=20)
        {"source": "PakPanang Direct", "group_en": "Vannamei Shrimp",
         "group_th": "กุ้งขาว", "category": "shrimp", "category_th": "กุ้ง",
         "option": "L", "scrape_date": "2026-05-09", "price_per_kg": 240.0,
         "selling_price": 240.0, "weight_kg": 1.0,
         "item_name_website": "v", "link": ""},
        # Slightly higher shelf price but qualifies for free delivery at 5kg
        {"source": "Sawasdee Seafood", "group_en": "Vannamei Shrimp",
         "group_th": "กุ้งขาว", "category": "shrimp", "category_th": "กุ้ง",
         "option": "L", "scrape_date": "2026-05-09", "price_per_kg": 250.0,
         "selling_price": 250.0, "weight_kg": 1.0,
         "item_name_website": "v", "link": ""},
    ]
    df = _make_df(rows)
    monkeypatch.setattr(mod, "load_seafood_data", lambda: df)
    monkeypatch.setattr(mod, "load_talaadthai_benchmark", lambda: pd.DataFrame())

    # 5kg order: Sawasdee 5×250=1250 ≥ free_threshold 1000 → ฿1250 total
    #            PakPanang 5×240 + 50 + 5×20 = 1200+50+100 = ฿1350
    # Sawasdee wins on landed cost despite higher shelf price.
    out = get_purchase_quote.invoke({"items": [{"species": "กุ้งขาว", "qty_kg": 5.0}]})
    assert "Sawasdee Seafood" in out
    assert "GRAND TOTAL" in out
