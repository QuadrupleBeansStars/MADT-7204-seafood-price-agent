"""
Tools for querying and comparing seafood prices.

These tools are bound to the LangGraph agent and called dynamically
based on user questions.  They read from the unified data layer
(``data.loader``) which handles both the registry CSV and scraped data.
"""

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from data.loader import (
    CATEGORY_MAP,
    CATEGORY_TH,
    VALID_CATEGORIES,
    has_historical_data,
    load_seafood_data,
    load_talaadthai_benchmark,
)
from data.transport_rates import estimate_transport


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


def _latest_per_shop_item(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse historical scrape rows to the latest per (source, group_en, option).

    The scraped CSV accumulates one row per shop+item+option per day. Tools
    that answer 'what's the price *now*' must dedupe to today's snapshot —
    otherwise the same shop appears N times (once per scrape day) and the
    agent shows 5 days of the same product as if they were 5 different
    offers (real bug observed in production).

    Rows without a parseable ``scrape_date`` (e.g. registry fallback) are
    kept as-is; they're treated as the "latest" by default since they have
    no timestamp to age out.
    """
    if df.empty or "scrape_date" not in df.columns:
        return df
    work = df.copy()
    work["_dt"] = pd.to_datetime(work["scrape_date"], errors="coerce")
    # Sort so most-recent rows come last; drop_duplicates(keep="last") then
    # keeps the freshest per shop+item+option. NaT sorts first, so dated
    # rows correctly win over timestamp-less ones.
    work = work.sort_values("_dt", na_position="first")
    work = work.drop_duplicates(
        subset=["source", "group_en", "option"], keep="last"
    )
    return work.drop(columns="_dt")


def _resolve_best_match(df: pd.DataFrame, item: str) -> tuple[pd.DataFrame, str | None]:
    """Pick the canonical species when *item* matches multiple group_en values.

    Generic queries like 'กุ้ง' (shrimp) match every shrimp species. Returning
    the first hit (e.g. 'Tiger Prawn') is wrong — feedback shows the agent
    must pick the species with the most cross-shop liquidity AND a Talaad
    Thai benchmark, so the user gets a statistically meaningful comparison.

    Ranking key per matched group_en:
        1. has Talaad Thai benchmark (True > False) — enables % vs market
        2. distinct shop count with a current price (more = better comparison)
        3. total row count (tiebreaker)

    If only one group_en matches, returns it unchanged with no note.
    Returns (filtered_df, note_for_agent).
    """
    matched = _match_item(df, item)
    if matched.empty:
        return matched, None
    groups = matched["group_en"].dropna().unique()
    if len(groups) <= 1:
        return matched, None

    benchmark_df = load_talaadthai_benchmark()
    benchmark_species = (
        set(benchmark_df["group_en"].dropna().tolist()) if not benchmark_df.empty else set()
    )

    priced = matched[matched["price_per_kg"].notna()]
    ranked = []
    for g in groups:
        g_priced = priced[priced["group_en"] == g]
        ranked.append((
            g,
            g in benchmark_species,
            g_priced["source"].nunique(),
            len(matched[matched["group_en"] == g]),
        ))
    # Sort: benchmark desc, shop_count desc, total desc
    ranked.sort(key=lambda r: (r[1], r[2], r[3]), reverse=True)
    winner, has_bench, shop_count, _ = ranked[0]

    th = matched[matched["group_en"] == winner]["group_th"].iloc[0] if not matched.empty else ""
    bench_note = "with market benchmark" if has_bench else "no market benchmark"
    others = ", ".join(g for g in groups if g != winner)
    note = (
        f"Query '{item}' matched multiple species. Picked {th} ({winner}) — "
        f"{shop_count} shops, {bench_note}. Other matches not shown: {others}."
    )
    return matched[matched["group_en"] == winner], note


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
    df = _latest_per_shop_item(load_seafood_data())
    result, best_match_note = _resolve_best_match(df, item)

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
    if best_match_note:
        lines.append(f"ℹ️ {best_match_note}\n")
    for _, row in result.iterrows():
        lines.append(_format_row(row))

    return "\n".join(lines)


def _landed_per_kg(row: pd.Series, basket_kg: float = 1.0) -> float:
    """Effective ฿/kg including amortised delivery fee for a *basket_kg* order.

    Uses the per-shop transport rate (data.transport_rates). The basket size
    matters because most shops have a free-delivery threshold — a 1kg basket
    rarely qualifies, a 5kg basket often does. Default 1kg gives a
    conservative (worst-case) landed cost for ranking single-item deals.
    """
    price_per_kg = row["price_per_kg"]
    if pd.isna(price_per_kg):
        return float("nan")
    order_value = float(price_per_kg) * basket_kg
    transport, _ = estimate_transport(row["source"], order_value, basket_kg)
    return float(price_per_kg) + (transport / basket_kg)


@tool
def get_best_deals(
    category: str | None = None,
) -> str:
    """Find seafood items priced well below the Talaad Thai market benchmark.

    Use this when the user asks for today's best deals, bargains, or biggest
    discounts. Ranking is based on **Total Landed Cost** (shop price +
    amortised delivery fee, computed from data.transport_rates), compared
    against the Talaad Thai wholesale benchmark — never a floating
    cross-shop average. Items with no benchmark are reported separately,
    not ranked as deals.

    Args:
        category: Optional category filter.  One of: fish, shrimp, squid,
                  crab, shellfish.  Also accepts Thai equivalents
                  (ปลา, กุ้ง, หมึก, ปู, หอย).
    """
    # Resolve Thai category names to English
    if category:
        cat_lower = category.strip().lower()
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

    df = _latest_per_shop_item(load_seafood_data())

    # Keep rows with a usable per-kg price. The loader has already filled
    # price_per_kg from selling_price/weight_kg where weight is known, so
    # pack items with declared weight ARE included here. Pack items with
    # unknown weight stay null and are surfaced separately below.
    priced = df[df["price_per_kg"].notna()].copy()
    pack_only = df[df["price_per_kg"].isna() & df["selling_price"].notna()].copy()

    if cat_lower:
        priced = priced[priced["category"] == cat_lower]
        pack_only = pack_only[pack_only["category"] == cat_lower]

    if priced.empty and pack_only.empty:
        cat_msg = f" for category '{category}'" if category else ""
        return f"No available inventory found{cat_msg}."

    # Talaad Thai benchmark — the *only* reference price we accept.
    bench = load_talaadthai_benchmark()
    if bench.empty:
        return (
            "No Talaad Thai benchmark available, so deals cannot be ranked "
            "honestly (a floating cross-shop average is not a real market "
            "price). Try `query_seafood_prices` for raw shop prices instead."
        )

    bench_lookup = bench.set_index("group_en")["price_per_kg"].to_dict()

    if priced.empty:
        analysis = pd.DataFrame()
    else:
        priced["benchmark_per_kg"] = priced["group_en"].map(bench_lookup)
        analysis = priced[priced["benchmark_per_kg"].notna()].copy()
        analysis["landed_per_kg"] = analysis.apply(_landed_per_kg, axis=1)
        analysis["pct_below_benchmark"] = (
            (analysis["benchmark_per_kg"] - analysis["landed_per_kg"])
            / analysis["benchmark_per_kg"]
        ) * 100

    deals = analysis[analysis["pct_below_benchmark"] > 10] if not analysis.empty else analysis
    cat_str = cat_lower if cat_lower else "all categories"

    lines: list[str] = []
    if deals.empty:
        lines.append(
            f"No items found priced 10%+ below the Talaad Thai benchmark "
            f"in {cat_str}."
        )
    else:
        top_deals = deals.sort_values("pct_below_benchmark", ascending=False).head(5)
        lines.append(
            f"Found {len(deals)} deals in {cat_str} — showing top 5 by "
            f"Total Landed Cost vs Talaad Thai benchmark.\n"
        )
        lines.append("Top Best Deals (landed cost = price + amortised delivery):")
        lines.append("-" * 60)
        for _, row in top_deals.iterrows():
            name = f"{row['group_th']} ({row['group_en']})"
            option_str = f" {row['option']}" if row["option"] != "-" else ""
            link_str = f"\n  🔗 {row['link']}" if row.get("link") else ""
            lines.append(
                f"• {name}{option_str} at {row['source']} | "
                f"Shelf: ฿{row['price_per_kg']:,.0f}/kg → "
                f"Landed: ฿{row['landed_per_kg']:,.0f}/kg | "
                f"Benchmark: ฿{row['benchmark_per_kg']:,.0f}/kg | "
                f"Save: {row['pct_below_benchmark']:.1f}%{link_str}"
            )

    # Surface pack-only items so the agent can still mention them
    if not pack_only.empty:
        lines.append("\nPack-only offers (weight unknown — not ranked):")
        lines.append("-" * 60)
        for _, row in pack_only.head(5).iterrows():
            name = f"{row['group_th']} ({row['group_en']})"
            option_str = f" {row['option']}" if row["option"] != "-" else ""
            link_str = f"\n  🔗 {row['link']}" if row.get("link") else ""
            lines.append(
                f"• {name}{option_str} at {row['source']} | "
                f"฿{row['selling_price']:,.0f} (pack){link_str}"
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

    # Prefer price_per_kg; fall back to selling_price for pack-only items (e.g. crab)
    has_ppkg = matched["price_per_kg"].notna().any()
    price_col = "price_per_kg" if has_ppkg else "selling_price"
    price_label = "฿/kg" if has_ppkg else "฿/pack"

    table = matched.pivot_table(
        index="scrape_date",
        columns="source",
        values=price_col,
        aggfunc="mean",
    ).sort_index()

    if table.empty or table.isna().all().all():
        group_name = matched.iloc[0]["group_en"]
        group_th = matched.iloc[0]["group_th"]
        return (
            f"📊 {group_th} ({group_name}) was found but has no numeric price data in the scrape. "
            f"The shop may not publish prices publicly."
        )

    summary = []
    for source in table.columns:
        prices = table[source].dropna()
        if len(prices) < 2:
            continue
        change_pct = ((prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]) * 100
        summary.append((source, change_pct))

    group_name = matched.iloc[0]["group_en"]
    group_th = matched.iloc[0]["group_th"]

    result = f"📊 Price trend for {group_th} ({group_name}) ({price_label}) — last {days} days\n\n"
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


# ── Pro-forma quote ──────────────────────────────────────────────────────────


class _QuoteItem(BaseModel):
    species: str = Field(description="Item name (English or Thai), e.g. 'shrimp', 'กุ้ง', 'squid'.")
    qty_kg: float = Field(description="Quantity in kilograms (must be > 0).", gt=0)


class _QuoteInput(BaseModel):
    items: list[_QuoteItem] = Field(
        description="List of seafood items with quantities to price.",
        min_length=1,
    )


@tool(args_schema=_QuoteInput)
def get_purchase_quote(items: list[dict]) -> str:
    """Generate a pro-forma quote for a multi-item seafood order.

    Use this when the user asks "if I buy X kg of A and Y kg of B, what's
    the total?" or wants a shopping plan with grand total. For each item:

      1. Resolves the species via Best-Match (highest-liquidity item with
         a Talaad Thai benchmark).
      2. Picks the shop with the lowest **Total Landed Cost** for the
         requested quantity (shelf price × qty + per-shop delivery fee
         from data.transport_rates, including free-delivery thresholds).
      3. Computes savings vs the Talaad Thai benchmark when available.

    Returns a line-by-line quote and a Grand Total row.

    Args:
        items: List of {species, qty_kg} entries.
    """
    df = _latest_per_shop_item(load_seafood_data())
    bench = load_talaadthai_benchmark()
    bench_lookup = (
        bench.set_index("group_en")["price_per_kg"].to_dict() if not bench.empty else {}
    )

    lines = ["Pro-forma quote (Total Landed Cost):", "=" * 60]
    grand_total = 0.0
    grand_benchmark = 0.0
    has_any_benchmark = False

    for entry in items:
        # Tool runtime hands us validated dicts (Pydantic schema above).
        species = entry["species"] if isinstance(entry, dict) else entry.species
        qty_kg = float(entry["qty_kg"] if isinstance(entry, dict) else entry.qty_kg)

        result, _ = _resolve_best_match(df, species)
        result = result[result["price_per_kg"].notna()]
        if result.empty:
            lines.append(f"\n• {species} ({qty_kg:g} kg) — no priced inventory found")
            continue

        # Score every shop's offer at the requested quantity, pick the cheapest.
        offers = []
        for _, row in result.iterrows():
            order_value = float(row["price_per_kg"]) * qty_kg
            transport, transport_note = estimate_transport(row["source"], order_value, qty_kg)
            line_total = order_value + transport
            offers.append((line_total, transport, transport_note, row))
        offers.sort(key=lambda o: o[0])
        best_total, best_transport, transport_note, best_row = offers[0]

        group_en = best_row["group_en"]
        group_th = best_row["group_th"]
        benchmark_per_kg = bench_lookup.get(group_en)
        benchmark_total = benchmark_per_kg * qty_kg if benchmark_per_kg else None
        if benchmark_total is not None:
            has_any_benchmark = True
            grand_benchmark += benchmark_total

        grand_total += best_total
        option_str = f" {best_row['option']}" if best_row["option"] != "-" else ""
        lines.append(
            f"\n• {group_th} ({group_en}){option_str} — {qty_kg:g} kg @ "
            f"฿{best_row['price_per_kg']:,.0f}/kg"
        )
        lines.append(f"   Shop:      {best_row['source']}")
        lines.append(
            f"   Subtotal:  ฿{best_row['price_per_kg'] * qty_kg:,.0f}  "
            f"+ delivery ฿{best_transport:,.0f} ({transport_note})"
        )
        lines.append(f"   Line total: ฿{best_total:,.0f}")
        if benchmark_total is not None:
            saving = benchmark_total - best_total
            pct = (saving / benchmark_total) * 100 if benchmark_total else 0.0
            lines.append(
                f"   Talaad Thai benchmark: ฿{benchmark_total:,.0f} "
                f"(save ฿{saving:,.0f}, {pct:+.1f}%)"
            )
        if best_row.get("link"):
            lines.append(f"   🔗 {best_row['link']}")

    lines.append("\n" + "=" * 60)
    lines.append(f"GRAND TOTAL: ฿{grand_total:,.0f}")
    if has_any_benchmark:
        diff = grand_benchmark - grand_total
        pct = (diff / grand_benchmark) * 100 if grand_benchmark else 0.0
        lines.append(
            f"vs Talaad Thai benchmark ฿{grand_benchmark:,.0f} → "
            f"save ฿{diff:,.0f} ({pct:+.1f}%)"
        )
    return "\n".join(lines)
