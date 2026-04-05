# Task 01 — `calculate_order_cost` Tool

**Branch:** `feature/tool-order-cost`
**File to edit:** `agent/tools/seafood_prices.py` and `agent/tools/__init__.py`
**Difficulty:** Beginner (vibe code friendly)

---

## What you're building

A new function that the AI agent can call when a user wants to know how much their seafood shopping list will cost at each shop — including a **transport fee** that goes up when oil prices are high.

This is one of the core business insights of the project: it's not just about seafood price, fuel costs affect delivery fees too.

---

## How it fits into the system

```
User asks: "I need 2kg of white shrimp and 1kg of sea bass — which shop is cheapest total?"
    │
    ▼
Agent (Gemini) decides to call: calculate_order_cost
    │  items = "white shrimp:2, sea bass:1"
    │  shop  = None  (compare all shops)
    ▼
Your tool queries the CSV for each item's price per shop
Adds transport fee: base fee + oil surcharge %
Returns a ranked table (cheapest shop first)
    │
    ▼
Agent reads your output and replies:
"Talad Thai is cheapest at ฿1,240 total (including ฿90 delivery).
 Or Tor Kor is ฿1,380 but has better availability."
```

---

## What the function should do

- Accept a comma-separated shopping list like `"white shrimp:2, sea bass:1"` (item:kg)
- Optionally accept a shop name to show only that shop
- Look up prices from `data/raw/seafood_prices_sample.csv`
- Add a transport fee per shop (use the config below)
- Return a formatted summary ranked cheapest-first

**Transport fee config** (hardcode this in the file):

```python
TRANSPORT_FEES = {
    "Talad Thai":               {"base_fee": 80,  "oil_surcharge_pct": 0.10},
    "Or Tor Kor Market":        {"base_fee": 60,  "oil_surcharge_pct": 0.08},
    "Makro":                    {"base_fee": 50,  "oil_surcharge_pct": 0.07},
    "Thai Market Bangkapi":     {"base_fee": 70,  "oil_surcharge_pct": 0.09},
    "Chatuchak Fish Market":    {"base_fee": 65,  "oil_surcharge_pct": 0.08},
}
```

Transport fee = `base_fee + (item_subtotal × oil_surcharge_pct)`

---

## Vibe-code prompt

Copy this and paste it into Claude or Gemini:

```
I'm building a LangChain tool for a seafood price comparison agent.
The tool is called calculate_order_cost.

Here is the existing code in agent/tools/seafood_prices.py:
[paste the full file content here]

Please add a new @tool function with this signature:
calculate_order_cost(items: str, shop: str | None = None, target_date: str | None = None) -> str

- items: comma-separated string like "white shrimp:2, sea bass:1" (item name : kg quantity)
- shop: optional — if given, show only that shop; if None, rank all shops cheapest-first
- target_date: optional YYYY-MM-DD, defaults to latest date in CSV

Use this transport fee config (hardcode it above the function):
TRANSPORT_FEES = {
    "Talad Thai":               {"base_fee": 80,  "oil_surcharge_pct": 0.10},
    "Or Tor Kor Market":        {"base_fee": 60,  "oil_surcharge_pct": 0.08},
    "Makro":                    {"base_fee": 50,  "oil_surcharge_pct": 0.07},
    "Thai Market Bangkapi":     {"base_fee": 70,  "oil_surcharge_pct": 0.09},
    "Chatuchak Fish Market":    {"base_fee": 65,  "oil_surcharge_pct": 0.08},
}

Transport fee = base_fee + (item_subtotal * oil_surcharge_pct)

Output format (per shop):
  Shop Name
    - white shrimp (2kg): ฿XXX
    - sea bass (1kg): ฿XXX
    Subtotal: ฿XXX | Transport: ฿XXX | TOTAL: ฿XXX

Rank shops cheapest total first. Mark out-of-stock items clearly.
Use the existing _load_prices() helper function.
```

---

## After generating the code

1. Paste the new function into `agent/tools/seafood_prices.py` (add it at the bottom)
2. Open `agent/tools/__init__.py` and add `calculate_order_cost` to the import and `ALL_TOOLS` list:

```python
from agent.tools.seafood_prices import query_seafood_prices, calculate_order_cost

ALL_TOOLS = [query_seafood_prices, calculate_order_cost]
```

---

## Git steps

```bash
git checkout main && git pull origin main
git checkout -b feature/tool-order-cost

# paste your generated code, save files

git add agent/tools/seafood_prices.py agent/tools/__init__.py
git commit -m "feat: add calculate_order_cost tool with oil surcharge transport fee"
git push origin feature/tool-order-cost
# open Pull Request on GitHub
```

---

## How to verify it works

Run this in terminal (from the repo root, with conda env active):

```bash
python -c "
from agent.tools.seafood_prices import calculate_order_cost
print(calculate_order_cost.invoke({'items': 'white shrimp:2, sea bass:1'}))
"
```

You should see a ranked table with item costs + transport fees + totals per shop.
