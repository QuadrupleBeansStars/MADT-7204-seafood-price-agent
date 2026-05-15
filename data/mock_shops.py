"""Synthetic price rows for 3 demo shops.

Prices are derived from real scraped data with a deterministic per-day
multiplier so trend charts show meaningful movement without introducing
random noise on each reload.
"""

import random

import pandas as pd

# Demo shops have no public storefront URL, so each carries a mock phone
# number instead. Downstream (_order_line in agent/tools/seafood_prices)
# falls back to this when a row has no link, so every row still shows an
# actionable way to buy.
MOCK_SHOPS = [
    {"name": "Gulf Fresh Co.", "bias": 1.05, "phone": "02-555-0188"},
    {"name": "PakPanang Direct", "bias": 0.95, "phone": "075-410-260"},
    {"name": "Cha-Am Seafood", "bias": 1.00, "phone": "032-471-339"},
]

_BASE_SOURCES = ["ไต้ก๋ง ซีฟู้ด", "PPNSeafood"]
_DAILY_NOISE = 0.08

# Demo undercut overrides: for each (shop, group_en), force that shop's row
# for the species to a fixed fraction of the Talaad Thai benchmark, so the
# demo can reliably show "ร้านนี้ถูกกว่าตลาดไท". One species → one shop, so
# only the designated shop undercuts (others stay at their bias-driven price)
# and the cross-shop comparison still has texture. Item-name override lets us
# show a specific size variant (e.g. "ตัวเล็กมาก").
_DEMO_UNDERCUT_OVERRIDES: list[dict] = [
    {
        "group_en": "Banana Prawn",
        "shop": "Gulf Fresh Co.",
        "tt_fraction": 0.78,
        "item_name": "กุ้งแชบ๊วย ตัวใหญ่",
        "option": "ขนาดใหญ่",
    },
    {
        "group_en": "Sea Bass",
        "shop": "PakPanang Direct",
        "tt_fraction": 0.72,
        "item_name": "ปลากะพงขาว สดจากบ่อ",
        "option": "ตัวละ 800-1000 กรัม",
    },
    {
        "group_en": "Blue Swimmer Crab",
        "shop": "Cha-Am Seafood",
        "tt_fraction": 0.62,
        "item_name": "ปูม้า เบอร์เล็ก",
        "option": "เบอร์เล็ก",
    },
    {
        "group_en": "Squid",
        "shop": "PakPanang Direct",
        "tt_fraction": 0.78,
        "item_name": "ปลาหมึกกล้วย ตัวเล็กมาก",
        "option": "ตัวเล็กมาก",
    },
]


def generate_mock_rows(real_df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of synthetic rows to merge with real scrape data."""
    if real_df is None or real_df.empty:
        return pd.DataFrame()

    base = real_df[
        real_df["source"].isin(_BASE_SOURCES) & real_df["price_per_kg"].notna()
    ].copy()

    if base.empty:
        return pd.DataFrame()

    dates = (
        sorted(real_df["scrape_date"].dropna().unique())
        if "scrape_date" in real_df.columns
        else [None]
    )

    all_rows = []
    for shop in MOCK_SHOPS:
        shop_name = shop["name"]
        bias = shop["bias"]

        for date in dates:
            date_base = base[base["scrape_date"] == date] if date is not None else base

            # One representative row per product group (cheapest from base sources)
            products = (
                date_base.sort_values("price_per_kg")
                .drop_duplicates(subset="group_en", keep="first")
            )

            for _, row in products.iterrows():
                rng = random.Random(f"{shop_name}|{date}|{row['group_en']}")
                daily_factor = 1.0 + rng.uniform(-_DAILY_NOISE, _DAILY_NOISE)
                multiplier = bias * daily_factor

                new_row = row.to_dict()
                new_row["source"] = shop_name
                new_row["price_per_kg"] = round(row["price_per_kg"] * multiplier, 0)
                if pd.notna(row.get("selling_price")):
                    new_row["selling_price"] = round(
                        float(row["selling_price"]) * multiplier, 0
                    )
                new_row["link"] = ""
                new_row["contact"] = shop["phone"]

                all_rows.append(new_row)

    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    if df.empty:
        return df
    return _apply_demo_undercuts(df, dates)


def _apply_demo_undercuts(df: pd.DataFrame, dates: list) -> pd.DataFrame:
    """Force the designated shop row for each demo species to a price clearly
    below the Talaad Thai benchmark for that species. Importing the
    benchmark loader lazily avoids a circular import (loader → mock_shops)."""
    try:
        from data.loader import load_talaadthai_benchmark
    except Exception:
        return df

    bench = load_talaadthai_benchmark()
    if bench.empty:
        return df
    bench_by_group = bench.set_index("group_en")["price_per_kg"].to_dict()

    for override in _DEMO_UNDERCUT_OVERRIDES:
        tt = bench_by_group.get(override["group_en"])
        if not tt:
            continue
        price = round(float(tt) * override["tt_fraction"], 0)
        mask = (df["source"] == override["shop"]) & (df["group_en"] == override["group_en"])
        if mask.any():
            df.loc[mask, "price_per_kg"] = price
            df.loc[mask, "selling_price"] = price
            df.loc[mask, "item_name_website"] = override["item_name"]
            df.loc[mask, "option"] = override["option"]
            df.loc[mask, "weight_kg"] = 1.0

    return df
