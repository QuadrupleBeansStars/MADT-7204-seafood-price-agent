import pandas as pd
from langchain_core.tools import tool


def _load_prices() -> pd.DataFrame:
    """Load CSV (works in both Colab and GitHub)"""
    try:
        df = pd.read_csv("data/raw/seafood_prices_sample.csv")  # GitHub
    except:
        df = pd.read_csv("seafood_prices_sample.csv")  # Colab

    df["date"] = pd.to_datetime(df["date"])
    df["available"] = df["available"].astype(bool)

    return df


@tool
def get_price_trend(item: str, days: int = 7) -> str:
    """Show price trend of an item over the last N days"""

    # --- validate days ---
    try:
        days = int(days)
        if days <= 0:
            return "❌ days must be a positive number"
    except:
        return "❌ days must be a number"

    df = _load_prices()

    # --- filter item ---
    df_filtered = df[df["item_name"].str.contains(item, case=False, na=False)]

    if df_filtered.empty:
        return f"❌ Item '{item}' not found"

    # --- get last N days ---
    unique_dates = sorted(df_filtered["date"].unique())[-days:]
    df_filtered = df_filtered[df_filtered["date"].isin(unique_dates)]

    # --- pivot table ---
    table = df_filtered.pivot_table(
        index="date",
        columns="shop",
        values="price_per_kg",
        aggfunc="mean"
    )

    table = table.sort_index()

    # --- summary ---
    summary = []

    for shop in table.columns:
        prices = table[shop].dropna()

        if len(prices) < 2:
            continue

        first = prices.iloc[0]
        last = prices.iloc[-1]

        change_pct = ((last - first) / first) * 100
        summary.append((shop, change_pct))

    if summary:
        max_up = max(summary, key=lambda x: x[1])
        max_down = min(summary, key=lambda x: x[1])

        summary_text = (
            f"\n📈 Highest increase: {max_up[0]} ({max_up[1]:.1f}%)"
            f"\n📉 Biggest decrease: {max_down[0]} ({max_down[1]:.1f}%)"
        )
    else:
        summary_text = "\nNo sufficient data for summary"

    # --- output ---
    result = f"📊 Price trend for '{item}' (last {days} days)\n\n"
    result += table.fillna("N/A").to_string()
    result += summary_text

    return result
