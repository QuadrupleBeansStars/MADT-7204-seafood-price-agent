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

from typing import Optional
import pandas as pd

def get_best_deals(category: Optional[str] = None, target_date: Optional[str] = None) -> str:
    """
    Scans the aggregator database to find seafood deals >10% below the market average.
    """
    VALID_CATEGORIES = {"fish", "shrimp", "squid", "crab", "shellfish"}
    FILE_PATH = "data/raw/seafood_prices_sample.csv"
    
    # 1. Input Validation
    if category and category.lower() not in VALID_CATEGORIES:
        return f"Error: '{category}' is an invalid category. Please choose from: {', '.join(VALID_CATEGORIES)}."
    
    try:
        df = pd.read_csv(FILE_PATH)
    except FileNotFoundError:
        return f"System Error: Could not locate data at {FILE_PATH}."

    # Normalize dates and handle the target_date logic
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    
    if target_date:
        if target_date not in df['date'].values:
            return f"Notice: No market data available for {target_date}. Please try another date."
        query_date = target_date
    else:
        query_date = df['date'].max()

    # 2. Data Filtering (Date, Availability, and Category)
    mask = (df['date'] == query_date) & (df['available'] == True)
    if category:
        mask &= (df['category'].str.lower() == category.lower())
        
    daily_df = df[mask].copy()

    if daily_df.empty:
        cat_msg = f" for category '{category}'" if category else ""
        return f"Notice: No available inventory found on {query_date}{cat_msg}."

    # 3. Market Computations
    market_stats = daily_df.groupby(['sku', 'item_name'])['price_per_kg'].agg(
        market_average='mean', 
        shop_count='count'
    ).reset_index()
    
    # Exclude items only sold by a single shop
    competitive_items = market_stats[market_stats['shop_count'] > 1]
    
    if competitive_items.empty:
        return f"No major deals found on {query_date}. Not enough cross-shop competition today."

    # Merge averages back with individual shop listings
    analysis_df = pd.merge(daily_df, competitive_items[['sku', 'market_average']], on='sku')
    
    # Calculate discount percentage
    analysis_df['pct_below_avg'] = ((analysis_df['market_average'] - analysis_df['price_per_kg']) / analysis_df['market_average']) * 100
    
    # 4. Extract Deals (> 10% below average)
    deals_df = analysis_df[analysis_df['pct_below_avg'] > 10].copy()
    
    total_deals = len(deals_df)
    if total_deals == 0:
        return f"No major deals found on {query_date}. Prices are quite stable across the board today!"
        
    # Sort deals largest to smallest discount and take top 5
    top_deals = deals_df.sort_values(by='pct_below_avg', ascending=False).head(5)
    
    # 5. Build Output String
    cat_str = category.lower() if category else "all categories"
    output = [f"Found {total_deals} deals today ({query_date}) across {cat_str} — showing top 5.\n"]
    output.append("Top Best Deals:")
    output.append("-" * 50)
    
    for _, row in top_deals.iterrows():
        output.append(
            f"• {row['item_name']} at {row['shop']} | "
            f"Price: ฿{row['price_per_kg']:.2f}/{row['unit']} | "
            f"Mkt Avg: ฿{row['market_average']:.2f} | "
            f"Save: {row['pct_below_avg']:.1f}%"
        )
        
    return "\n".join(output)

