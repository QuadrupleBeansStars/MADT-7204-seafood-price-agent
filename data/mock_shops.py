"""Synthetic price rows for 3 demo shops.

Prices are derived from real scraped data with a deterministic per-day
multiplier so trend charts show meaningful movement without introducing
random noise on each reload.
"""

import random

import pandas as pd

MOCK_SHOPS = [
    {"name": "Gulf Fresh Co.", "bias": 1.05},
    {"name": "PakPanang Direct", "bias": 0.95},
    {"name": "Cha-Am Seafood", "bias": 1.00},
]

_BASE_SOURCES = ["ไต้ก๋ง ซีฟู้ด", "PPNSeafood"]
_DAILY_NOISE = 0.08


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

                all_rows.append(new_row)

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
