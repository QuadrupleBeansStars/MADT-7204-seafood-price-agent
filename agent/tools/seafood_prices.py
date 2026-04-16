"""
Tools for querying and comparing seafood prices.

These tools are bound to the LangGraph agent and called dynamically
based on user questions.
"""

from datetime import date
from pathlib import Path

import pandas as pd
from langchain_core.tools import tool

DATA_PATH = Path(__file__).parent.parent.parent / "data" / "raw" / "seafood_prices_sample.csv"

VALID_CATEGORIES = {"fish", "shrimp", "squid", "crab", "shellfish"}


def _load_prices() -> pd.DataFrame:
    """Load the seafood prices CSV into a DataFrame."""
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["available"] = df["available"].astype(bool)
    return df


@tool
def query_seafood_prices(
    item: str,
    shop: str | None = None,
    target_date: str | None = None,
) -> str:
    """Query seafood prices by item name, optionally filtered by shop and date.

    Use this tool when the user asks about prices for a specific seafood item.

    Args:
        item: Seafood item to search for (e.g. 'shrimp', 'salmon', 'crab').
              Matches against item_name (case-insensitive partial match).
        shop: Optional shop name to filter by (e.g. 'Talad Thai', 'Makro').
        target_date: Optional date string in YYYY-MM-DD format. Defaults to latest date.
    """
    df = _load_prices()

    mask = df["item_name"].str.contains(item, case=False, na=False)
    result = df[mask]

    if result.empty:
        return f"No results found for '{item}'. Available categories: shrimp, fish, squid, crab, shellfish."

    if shop:
        shop_mask = result["shop"].str.contains(shop, case=False, na=False)
        result = result[shop_mask]
        if result.empty:
            return f"No results for '{item}' at shop matching '{shop}'."

    if target_date:
        result = result[result["date"] == date.fromisoformat(target_date)]
    else:
        latest_date = result["date"].max()
        result = result[result["date"] == latest_date]

    if result.empty:
        return "No data found for the specified date."

    lines = [f"Seafood prices for '{item}' ({result.iloc[0]['date']}):\n"]
    for _, row in result.iterrows():
        status = "In Stock" if row["available"] else "OUT OF STOCK"
        lines.append(
            f"  {row['shop']:25s} | {row['item_name']:25s} | "
            f"฿{row['price_per_kg']:>8.1f}/{row['unit']} | {status}"
        )

    return "\n".join(lines)


@tool
def get_best_deals(
    category: str | None = None,
    target_date: str | None = None,
) -> str:
    """Find seafood deals priced >10% below the market average.

    Use this when the user asks for today's best deals, bargains, or biggest
    discounts. Returns up to 5 deals sorted by largest discount first.

    Args:
        category: Optional category filter (fish, shrimp, squid, crab, shellfish).
        target_date: Optional date string in YYYY-MM-DD format. Defaults to latest date.
    """
    if category and category.lower() not in VALID_CATEGORIES:
        return f"Error: '{category}' is an invalid category. Please choose from: {', '.join(sorted(VALID_CATEGORIES))}."

    df = _load_prices()

    if target_date:
        query_date = date.fromisoformat(target_date)
        if query_date not in df["date"].values:
            return f"Notice: No market data available for {target_date}. Please try another date."
    else:
        query_date = df["date"].max()

    mask = (df["date"] == query_date) & df["available"]
    if category:
        mask &= df["category"].str.lower() == category.lower()

    daily_df = df[mask].copy()

    if daily_df.empty:
        cat_msg = f" for category '{category}'" if category else ""
        return f"Notice: No available inventory found on {query_date}{cat_msg}."

    market_stats = daily_df.groupby(["sku", "item_name"])["price_per_kg"].agg(
        market_average="mean",
        shop_count="count",
    ).reset_index()

    competitive_items = market_stats[market_stats["shop_count"] > 1]

    if competitive_items.empty:
        return f"No major deals found on {query_date}. Not enough cross-shop competition today."

    analysis_df = pd.merge(daily_df, competitive_items[["sku", "market_average"]], on="sku")
    analysis_df["pct_below_avg"] = (
        (analysis_df["market_average"] - analysis_df["price_per_kg"])
        / analysis_df["market_average"]
    ) * 100

    deals_df = analysis_df[analysis_df["pct_below_avg"] > 10]

    if deals_df.empty:
        return f"No major deals found on {query_date}. Prices are quite stable across the board today!"

    top_deals = deals_df.sort_values(by="pct_below_avg", ascending=False).head(5)

    cat_str = category.lower() if category else "all categories"
    lines = [f"Found {len(deals_df)} deals today ({query_date}) across {cat_str} — showing top 5.\n"]
    lines.append("Top Best Deals:")
    lines.append("-" * 50)

    for _, row in top_deals.iterrows():
        lines.append(
            f"• {row['item_name']} at {row['shop']} | "
            f"Price: ฿{row['price_per_kg']:.2f}/{row['unit']} | "
            f"Mkt Avg: ฿{row['market_average']:.2f} | "
            f"Save: {row['pct_below_avg']:.1f}%"
        )

    return "\n".join(lines)


@tool
def get_price_trend(item: str, days: int = 7) -> str:
    """Show price trend of an item across shops over the last N days.

    Use this when the user asks about price history, price trends, or how
    a seafood item's price has changed recently.

    Args:
        item: Seafood item name (case-insensitive partial match).
        days: Number of most-recent days to include. Defaults to 7.
    """
    if days <= 0:
        return "days must be a positive number"

    df = _load_prices()

    df_filtered = df[df["item_name"].str.contains(item, case=False, na=False)]

    if df_filtered.empty:
        return f"Item '{item}' not found."

    unique_dates = sorted(df_filtered["date"].unique())[-days:]
    df_filtered = df_filtered[df_filtered["date"].isin(unique_dates)]

    table = df_filtered.pivot_table(
        index="date",
        columns="shop",
        values="price_per_kg",
        aggfunc="mean",
    ).sort_index()

    summary = []
    for shop in table.columns:
        prices = table[shop].dropna()
        if len(prices) < 2:
            continue
        change_pct = ((prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]) * 100
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

    result = f"📊 Price trend for '{item}' (last {days} days)\n\n"
    result += table.fillna("N/A").to_string()
    result += summary_text

    return result
