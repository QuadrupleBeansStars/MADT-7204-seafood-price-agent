"""Transport/delivery rates per shop, assuming Greater Bangkok delivery.

"Greater Bangkok" = the BKK metropolis + the 5 adjacent provinces
(Nakhon Pathom, Pathum Thani, Nonthaburi, Samut Prakan, Samut Sakhon).
Rates here are the user-facing default for our app's audience (we serve
restaurants, wholesalers, and households in Bangkok).

Structure per shop:
  flat           — flat delivery fee in THB (always charged unless waived)
  free_threshold — order value (THB) above which delivery is free; None = never free
  per_kg         — additional per-kg charge on top of flat; None = flat only

Sources (verified from shop websites, May 2026):
  - sirinfarm:        ฿70 flat, free over ฿2,000 (sirinfarm.com)
  - PPNSeafood:       ฿130 flat (ppnseafoodwishing.com)
  - taikong / ไต้ก๋ง: ฿250 flat nationwide (taikongseafood.com)
  - HENG HENG:        free everywhere (henghengseafood.com "ส่งฟรีทั่วไทย")
  - Sawasdee:         free (sawasdeeseafood.com "ค่าจัดส่งฟรี")
  - supreme seafoods: free (supremeseafoods.net "ค่าจัดส่งฟรี")
  - siriratseafood:   free (siriratseafood.com "ค่าจัดส่งฟรี")
"""

TRANSPORT_RATES: dict[str, dict] = {
    # Real shops — verified from shop websites for Greater Bangkok delivery
    "ไต้ก๋ง ซีฟู้ด":    {"flat": 250, "free_threshold": None, "per_kg": None},
    "Sawasdee Seafood":  {"flat": 0,   "free_threshold": None, "per_kg": None},
    "HENG HENG Seafood": {"flat": 0,   "free_threshold": None, "per_kg": None},
    "PPNSeafood":         {"flat": 130, "free_threshold": None, "per_kg": None},
    "supreme seafoods":   {"flat": 0,   "free_threshold": None, "per_kg": None},
    "siriratseafood":     {"flat": 0,   "free_threshold": None, "per_kg": None},
    "sirinfarm":          {"flat": 70,  "free_threshold": 2000, "per_kg": None},
    # Mock / demo shops — kept synthetic so the dataset still has variety
    # for cross-shop comparison demos when free-shipping shops dominate.
    "Gulf Fresh Co.":    {"flat": 130, "free_threshold": 1800, "per_kg": None},
    "PakPanang Direct":  {"flat": 50,  "free_threshold": None, "per_kg": 20},
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
