# Task 01 — `calculate_order_cost` Tool

**Branch:** `feature/tool-order-cost`
**File to edit:** `agent/tools/seafood_prices.py` and `agent/tools/__init__.py`

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

## Thinking steps

Before you ask an AI to write the code, think through these questions first. Your answers will help you write a much better prompt.

1. **What does the input look like?** The `items` parameter is a string. How do you split it into individual items? What if there's extra whitespace? What if the user types `"shrimp:2"` vs `"shrimp : 2"` — should both work?

2. **How do you match item names?** The user types `"white shrimp"` but the CSV has `"White Shrimp (Large)"`. Should the match be exact, or partial? Case-sensitive or not?

3. **What if a shop is given?** If `shop = "Makro"`, you only calculate for that one shop. But what if the user types `"makro"` in lowercase — does it still find it?

4. **What if an item is out of stock at a shop?** Can you still include that shop in the total, or should you skip it and warn the user?

5. **What order should the output be in?** If no shop is specified, how do you rank them? Cheapest grand total first?

6. **What should the output look like?** Think about what a user would want to see: item-by-item breakdown, subtotal, transport fee, grand total.

Once you've thought through these, you're ready to write your vibe-code prompt and ask the AI to build it.

---

## Acceptance criteria

Your task is complete when all of the following work correctly:

**Basic cases:**
- [ ] Single item, no shop → returns cost breakdown for all 5 shops, ranked cheapest first
- [ ] Multiple items, no shop → sums all items per shop, adds transport, ranks correctly
- [ ] Single item, specific shop → returns only that shop's breakdown
- [ ] Multiple items, specific shop → returns only that shop's breakdown with correct totals

**Edge cases:**
- [ ] Item name doesn't exist in CSV → returns a helpful message like `"Item 'lobster' not found. Did you mean: ...?"` or lists available items
- [ ] One item in the list doesn't exist, others do → calculates what it can, warns about the missing item
- [ ] Shop name doesn't exist → returns a helpful message listing the valid shop names
- [ ] Shop name is given in wrong case (e.g. `"makro"` instead of `"Makro"`) → still finds it (case-insensitive match)
- [ ] An item is out of stock at some shops → marks those shops clearly, still shows their price if available, or skips them with a note
- [ ] Items string has extra spaces or inconsistent formatting → still parses correctly

**Output quality:**
- [ ] Grand total per shop includes both item cost and transport fee
- [ ] Transport fee is visible separately (not hidden in the total)
- [ ] Oil surcharge % is mentioned so users understand why transport isn't flat

---

## After writing the code

1. Paste the new function into `agent/tools/seafood_prices.py` (add at the bottom)
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

# save your file changes

git add agent/tools/seafood_prices.py agent/tools/__init__.py
git commit -m "feat: add calculate_order_cost tool with oil surcharge transport fee"
git push origin feature/tool-order-cost
# open Pull Request on GitHub
```

---

## How to verify it works

Run these test cases from the terminal (repo root, conda env active):

```bash
python -c "
from agent.tools.seafood_prices import calculate_order_cost

# Basic: single item, all shops
print(calculate_order_cost.invoke({'items': 'white shrimp:2'}))
print('---')
# Multiple items, all shops
print(calculate_order_cost.invoke({'items': 'white shrimp:2, sea bass:1'}))
print('---')
# Specific shop
print(calculate_order_cost.invoke({'items': 'white shrimp:2', 'shop': 'Makro'}))
print('---')
# Item not found
print(calculate_order_cost.invoke({'items': 'dragon fish:1'}))
print('---')
# Shop not found
print(calculate_order_cost.invoke({'items': 'white shrimp:1', 'shop': 'Big C'}))
"
```
