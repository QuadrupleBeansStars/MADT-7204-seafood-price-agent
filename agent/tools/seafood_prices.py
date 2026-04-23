"""
Tools for querying and comparing seafood prices.

These tools are bound to the LangGraph agent and called dynamically
based on user questions.  They read from the unified data layer
(``data.loader``) which handles both the registry CSV and scraped data.
"""

import pandas as pd
from langchain_core.tools import tool

from data.loader import (
    CATEGORY_MAP,
    CATEGORY_TH,
    VALID_CATEGORIES,
    has_historical_data,
    load_seafood_data,
)


def _match_item(df: pd.DataFrame, item: str) -> pd.DataFrame:
    """Return rows matching *item* across all name/category columns."""
    q = item.strip()
    mask = (
        df["group_en"].str.contains(q, case=False, na=False)
        | df["group_th"].str.contains(q, case=False, na=False)
        | df["item_name_website"].str.contains(q, case=False, na=False)
        | df["category"].str.contains(q, case=False, na=False)
        | df["category_th"].str.contains(q, case=False, na=False)
    )
    return df[mask]


def _format_row(row: pd.Series) -> str:
    """Format a single product row for the agent's text response."""
    name = f"{row['group_th']} ({row['group_en']})"
    option_str = f" | {row['option']}" if row["option"] != "-" else ""
    if pd.notna(row["price_per_kg"]):
        price_str = f"฿{row['price_per_kg']:,.0f}/kg"
    else:
        price_str = f"฿{row['selling_price']:,.0f} (pack)"
    link_str = f"\n  🔗 {row['link']}" if row["link"] else ""
    return f"  {row['source']:25s} | {name}{option_str} | {price_str}{link_str}"


@tool
def query_seafood_prices(
    item: str,
    shop: str | None = None,
) -> str:
    """Query seafood prices by item name, optionally filtered by shop.

    Use this tool when the user asks about prices for a specific seafood
    item.  Searches across English names, Thai names, and categories.

    Args:
        item: Seafood item to search for (e.g. 'shrimp', 'salmon', 'กุ้ง',
              'ปลาแซลมอน').  Case-insensitive partial match.
        shop: Optional shop/source name to filter by (e.g. 'PPNSeafood',
              'ไต้ก๋ง').  Case-insensitive partial match.
    """
    df = load_seafood_data()
    result = _match_item(df, item)

    if result.empty:
        cats = ", ".join(sorted(VALID_CATEGORIES))
        return (
            f"No results found for '{item}'. "
            f"Try searching by category ({cats}) or Thai name."
        )

    if shop:
        shop_mask = result["source"].str.contains(shop, case=False, na=False)
        result = result[shop_mask]
        if result.empty:
            return f"No results for '{item}' at shop matching '{shop}'."

    lines = [f"Seafood prices for '{item}':\n"]
    for _, row in result.iterrows():
        lines.append(_format_row(row))

    return "\n".join(lines)


@tool
def get_best_deals(
    category: str | None = None,
) -> str:
    """Find seafood items priced well below the group average across shops.

    Use this when the user asks for today's best deals, bargains, or
    biggest discounts.  Returns up to 5 deals sorted by largest discount.

    Args:
        category: Optional category filter.  One of: fish, shrimp, squid,
                  crab, shellfish.  Also accepts Thai equivalents
                  (ปลา, กุ้ง, หมึก, ปู, หอย).
    """
    # Resolve Thai category names to English
    if category:
        cat_lower = category.strip().lower()
        # Check if it's a Thai category name
        th_to_en = {v: k for k, v in CATEGORY_TH.items()}
        if cat_lower in th_to_en:
            cat_lower = th_to_en[cat_lower]
        if cat_lower not in VALID_CATEGORIES:
            return (
                f"Error: '{category}' is an invalid category. "
                f"Please choose from: {', '.join(sorted(VALID_CATEGORIES))} "
                f"(or Thai: {', '.join(CATEGORY_TH[c] for c in sorted(VALID_CATEGORIES))})."
            )
    else:
        cat_lower = None

    df = load_seafood_data()

    # Only rows with price_per_kg for fair comparison
    df = df[df["price_per_kg"].notna()].copy()

    if cat_lower:
        df = df[df["category"] == cat_lower]

    if df.empty:
        cat_msg = f" for category '{category}'" if category else ""
        return f"No available inventory found{cat_msg}."

    # Compute group average price_per_kg across sources
    group_avg = (
        df.groupby("group_en")["price_per_kg"]
        .agg(market_average="mean", shop_count="count")
        .reset_index()
    )

    # Only groups with 2+ sources for meaningful comparison
    competitive = group_avg[group_avg["shop_count"] > 1]
    if competitive.empty:
        return "No major deals found. Not enough cross-shop competition."

    analysis = df.merge(competitive[["group_en", "market_average"]], on="group_en")
    analysis["pct_below_avg"] = (
        (analysis["market_average"] - analysis["price_per_kg"])
        / analysis["market_average"]
    ) * 100

    deals = analysis[analysis["pct_below_avg"] > 10]
    if deals.empty:
        return "No major deals found. Prices are quite stable across shops!"

    top_deals = deals.sort_values("pct_below_avg", ascending=False).head(5)

    cat_str = cat_lower if cat_lower else "all categories"
    lines = [
        f"Found {len(deals)} deals across {cat_str} — showing top 5.\n",
        "Top Best Deals:",
        "-" * 50,
    ]

    for _, row in top_deals.iterrows():
        name = f"{row['group_th']} ({row['group_en']})"
        option_str = f" {row['option']}" if row["option"] != "-" else ""
        link_str = f"\n  🔗 {row['link']}" if row.get("link") else ""
        lines.append(
            f"• {name}{option_str} at {row['source']} | "
            f"Price: ฿{row['price_per_kg']:,.0f}/kg | "
            f"Avg: ฿{row['market_average']:,.0f}/kg | "
            f"Save: {row['pct_below_avg']:.1f}%{link_str}"
        )

    return "\n".join(lines)


@tool
def get_price_trend(item: str, days: int = 7) -> str:
    """Show price trend of an item across shops over the last N days.

    Use this when the user asks about price history, price trends, or how
    a seafood item's price has changed recently.

    Args:
        item: Seafood item name (case-insensitive partial match).
              Accepts English or Thai names.
        days: Number of most-recent days to include.  Defaults to 7.
    """
    if days <= 0:
        return "days must be a positive number."

    if not has_historical_data():
        # Fall back: show price spread across shops as a proxy
        df = load_seafood_data()
        matched = _match_item(df, item)
        if matched.empty:
            return f"Item '{item}' not found."

        with_price = matched[matched["price_per_kg"].notna()]
        if with_price.empty:
            return f"No price-per-kg data available for '{item}'."

        group_name = with_price.iloc[0]["group_en"]
        group_th = with_price.iloc[0]["group_th"]

        lines = [
            f"📊 Price comparison for {group_th} ({group_name})\n",
            "⚠️ Historical trend data requires multiple daily scrapes. "
            "Showing current price spread across shops instead.\n",
        ]
        for _, row in with_price.iterrows():
            option_str = f" ({row['option']})" if row["option"] != "-" else ""
            link_str = f" 🔗 {row['link']}" if row["link"] else ""
            lines.append(
                f"  {row['source']:25s} | {option_str:20s} | "
                f"฿{row['price_per_kg']:,.0f}/kg{link_str}"
            )

        prices = with_price["price_per_kg"]
        lines.append(f"\nMin: ฿{prices.min():,.0f}/kg | Max: ฿{prices.max():,.0f}/kg | "
                      f"Spread: ฿{prices.max() - prices.min():,.0f}")
        return "\n".join(lines)

    # Historical mode — scraped CSV has multiple dates
    df = load_seafood_data()
    matched = _match_item(df, item)
    if matched.empty:
        return f"Item '{item}' not found."

    if "scrape_date" not in matched.columns:
        return "No date information available in the data."

    matched["scrape_date"] = pd.to_datetime(matched["scrape_date"], errors="coerce").dt.date
    matched = matched[matched["scrape_date"].notna()]  # drop registry-only rows (no scrape date)
    if matched.empty:
        return f"No historical scrape data found for '{item}'. Try querying current prices instead."
    unique_dates = sorted(matched["scrape_date"].unique())[-days:]
    matched = matched[matched["scrape_date"].isin(unique_dates)]

    table = matched.pivot_table(
        index="scrape_date",
        columns="source",
        values="price_per_kg",
        aggfunc="mean",
    ).sort_index()

    summary = []
    for source in table.columns:
        prices = table[source].dropna()
        if len(prices) < 2:
            continue
        change_pct = ((prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]) * 100
        summary.append((source, change_pct))

    group_name = matched.iloc[0]["group_en"]
    group_th = matched.iloc[0]["group_th"]

    result = f"📊 Price trend for {group_th} ({group_name}) — last {days} days\n\n"
    result += table.fillna("N/A").to_string()

    if summary:
        max_up = max(summary, key=lambda x: x[1])
        max_down = min(summary, key=lambda x: x[1])
        result += (
            f"\n\n📈 Highest increase: {max_up[0]} ({max_up[1]:+.1f}%)"
            f"\n📉 Biggest decrease: {max_down[0]} ({max_down[1]:+.1f}%)"
        )
    else:
        result += "\n\nNot enough data points for trend summary."

    return result
