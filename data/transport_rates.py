"""Placeholder transport/delivery rates per shop.

Structure per shop:
  flat           — flat delivery fee in THB (always charged unless waived)
  free_threshold — order value (THB) above which delivery is free; None = never free
  per_kg         — additional per-kg charge on top of flat; None = flat only

Update these with actual shop policies once confirmed.
"""

TRANSPORT_RATES: dict[str, dict] = {
    "ไต้ก๋ง ซีฟู้ด":    {"flat": 100, "free_threshold": 1500, "per_kg": None},
    "Sawasdee Seafood":  {"flat": 80,  "free_threshold": 1000, "per_kg": None},
    "HENG HENG Seafood": {"flat": 120, "free_threshold": None,  "per_kg": None},
    "PPNSeafood":         {"flat": 90,  "free_threshold": 1200, "per_kg": None},
    "supreme seafoods":   {"flat": 150, "free_threshold": 2000, "per_kg": None},
    "siriratseafood":     {"flat": 70,  "free_threshold": 800,  "per_kg": None},
    "sirinfarm":          {"flat": 60,  "free_threshold": 500,  "per_kg": None},
    # mock / demo shops
    "Gulf Fresh Co.":    {"flat": 130, "free_threshold": 1800, "per_kg": None},
    "PakPanang Direct":  {"flat": 50,  "free_threshold": None,  "per_kg": 20},
    "Cha-Am Seafood":    {"flat": 90,  "free_threshold": 1000, "per_kg": None},
}


def estimate_transport(shop: str, order_value_thb: float, qty_kg: float) -> tuple[float, str]:
    """Return (transport_cost_thb, human_readable_note) for a shop and order."""
    rates = TRANSPORT_RATES.get(shop)
    if rates is None:
        return 0.0, "Unknown shop"

    flat = rates["flat"]
    threshold = rates["free_threshold"]
    per_kg = rates["per_kg"]

    if threshold is not None and order_value_thb >= threshold:
        return 0.0, f"Free delivery (order ≥ ฿{threshold:,})"

    cost = float(flat)
    if per_kg is not None:
        cost += per_kg * qty_kg
        note = f"฿{flat} + ฿{per_kg}/kg"
    else:
        note = f"฿{flat} flat rate"

    return cost, note
