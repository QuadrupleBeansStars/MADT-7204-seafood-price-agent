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

    # Filter by item (case-insensitive partial match)
    mask = df["item_name"].str.contains(item, case=False, na=False)
    result = df[mask]

    if result.empty:
        return f"No results found for '{item}'. Available categories: shrimp, fish, squid, crab, shellfish."

    # Filter by shop
    if shop:
        shop_mask = result["shop"].str.contains(shop, case=False, na=False)
        result = result[shop_mask]
        if result.empty:
            return f"No results for '{item}' at shop matching '{shop}'."

    # Filter by date
    if target_date:
        result = result[result["date"] == date.fromisoformat(target_date)]
    else:
        latest_date = result["date"].max()
        result = result[result["date"] == latest_date]

    if result.empty:
        return "No data found for the specified date."

    # Format output
    lines = [f"Seafood prices for '{item}' ({result.iloc[0]['date']}):\n"]
    for _, row in result.iterrows():
        status = "In Stock" if row["available"] else "OUT OF STOCK"
        lines.append(
            f"  {row['shop']:25s} | {row['item_name']:25s} | "
            f"฿{row['price_per_kg']:>8.1f}/{row['unit']} | {status}"
        )

    return "\n".join(lines)


