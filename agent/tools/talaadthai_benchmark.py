"""`get_talaadthai_benchmark` agent tool.

Returns the Talaad Thai wholesale market reference price (ราคากลาง) for a
species, so the agent can benchmark a supplier's quote against it and tell
the user how good the deal really is.
"""

from __future__ import annotations

from langchain_core.tools import tool

from data.loader import load_talaadthai_benchmark


def _match_row(species: str):
    df = load_talaadthai_benchmark()
    if df.empty:
        return None
    q = (species or "").strip()
    if not q:
        return None
    mask = (
        df["group_en"].str.contains(q, case=False, na=False)
        | df["group_th"].str.contains(q, case=False, na=False)
    )
    sub = df[mask]
    if sub.empty:
        return None
    # Prefer exact group_en match if there are multiple
    exact = sub[sub["group_en"].str.casefold() == q.casefold()]
    return (exact.iloc[0] if not exact.empty else sub.iloc[0])


@tool
def get_talaadthai_benchmark(species: str) -> dict:
    """Talaad Thai wholesale market reference price for a species (ราคากลาง).

    Use this on EVERY user price query, after locating the supplier price(s),
    so you can frame the answer with the percent difference vs. the market
    benchmark. Talaad Thai is a wholesale market — not a shop the user
    orders from — so its price is the reference, not an option to buy.

    The returned price_per_kg is in ฿/kg, the same unit as every supplier
    price — safe to compute a percentage difference directly.

    Args:
        species: English or Thai species name (partial match accepted, e.g.
                 "white shrimp", "กุ้งขาว", "salmon").

    Returns:
        dict with:
            found: bool
            unit: always "THB/kg" — comparison only valid against per-kg prices
            group_en, group_th: matched species names
            price_per_kg: mean THB/kg across size variants (the headline)
            price_min, price_max: range across size variants
            n_variants: how many variants were averaged
            snapshot_date: ISO date of the latest underlying TT snapshot
            link: URL to the most recent variant
        When no benchmark exists for the species:
            {"found": False, "species": <input>}
    """
    row = _match_row(species)
    if row is None:
        return {"found": False, "species": species}
    return {
        "found": True,
        "unit": "THB/kg",
        "group_en": row["group_en"],
        "group_th": row["group_th"],
        "price_per_kg": float(row["price_per_kg"]),
        "price_min": float(row["price_min"]),
        "price_max": float(row["price_max"]),
        "n_variants": int(row["n_variants"]),
        "snapshot_date": (
            row["snapshot_date"].date().isoformat()
            if hasattr(row["snapshot_date"], "date") and row["snapshot_date"] is not None
            else None
        ),
        "link": row["link"] if isinstance(row["link"], str) else "",
    }
