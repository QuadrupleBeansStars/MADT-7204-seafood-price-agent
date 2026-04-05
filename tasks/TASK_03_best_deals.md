# Task 03 — `get_best_deals` Tool

**Branch:** `feature/tool-best-deals`
**File to edit:** `agent/tools/seafood_prices.py` and `agent/tools/__init__.py`

---

## What you're building

A "morning market summary" function — when called with no arguments, it scans today's prices across all shops and highlights the best deals (items priced significantly below the market average). Users can also filter by category.

This replaces the old `compare_prices` tool with something smarter and more business-oriented.

---

## How it fits into the system

```
User asks: "What are the best seafood deals today?"
    │
    ▼
Agent (Gemini) decides to call: get_best_deals
    │  category = None  (show all categories)
    │  target_date = None  (use latest date)
    ▼
Your tool scans today's prices across all shops
Calculates market average per item
Flags items priced >10% below average as "deals"
Returns a ranked list of best deals
    │
    ▼
Agent reads your output and replies:
"Today's best deals:
 1. White Shrimp at Talad Thai — ฿250/kg (18% below average)
 2. Tilapia at Makro — ฿95/kg (12% below average)
 3. Squid at Thai Market Bangkapi — ฿170/kg (11% below average)"
```

---

## What the function should do

- Accept an optional `category` ("fish", "shrimp", "squid", "crab", "shellfish") and optional `target_date`
- Load the latest day's data from `data/raw/seafood_prices_sample.csv`
- For each item, calculate the average price across all shops (available only)
- Flag items where a shop's price is more than 10% below the average as a "deal"
- Return the top deals sorted by % discount (biggest saving first)
- Include: shop name, item name, price, market avg, % below average

---

## Thinking steps

Before you ask an AI to write the code, think through these questions:

1. **What counts as a "deal"?** The threshold is >10% below the market average for that item. How do you calculate the market average — average of all shops, or only shops that have it in stock?

2. **What if there are no deals today?** Prices might all be close to average on a given day. What should the function return in that case?

3. **What if a category filter is given but doesn't match anything?** E.g. `category = "lobster"` — should you return an error or an empty result with a message?

4. **How do you rank the deals?** By % discount? By absolute ฿ savings? Decide what makes most sense for a restaurant buyer.

5. **How many deals should you show?** All of them, or a top N? Think about what's useful — a wall of 30 deals is overwhelming; a top 5 or top 10 is actionable.

6. **What if the same item has multiple shop entries?** One item might appear at 5 shops. Only the shops with price below average should be flagged as deals.

---

## Acceptance criteria

Your task is complete when all of the following work correctly:

**Basic cases:**
- [ ] No arguments → scans all categories for today's latest date, returns top deals ranked by % discount
- [ ] `category = "fish"` → returns only fish deals
- [ ] `category = "shrimp"` → returns only shrimp deals
- [ ] `target_date` given → scans that specific date instead of the latest

**Edge cases:**
- [ ] No deals found on a given date → returns a friendly message instead of an empty response
- [ ] Category filter doesn't match any known category → returns an error message listing the valid categories
- [ ] `target_date` given but no data exists for that date → returns a helpful message
- [ ] All items at a shop are out of stock → those items are excluded from deal calculations
- [ ] Only one shop has an item in stock → market average = that shop's price, so no deal can be flagged (handle gracefully)

**Output quality:**
- [ ] Each deal entry clearly shows: shop name, item name, price, market average, and % savings
- [ ] The output is useful to a restaurant buyer making a morning purchasing decision
- [ ] Total number of deals found is mentioned (e.g. "Found 6 deals today across all categories")

---

## After writing the code

1. Paste the new function into `agent/tools/seafood_prices.py` (add at the bottom)
2. Open `agent/tools/__init__.py` and add `get_best_deals`:

```python
from agent.tools.seafood_prices import query_seafood_prices, get_best_deals

ALL_TOOLS = [query_seafood_prices, get_best_deals]
```

---

## Git steps

```bash
git checkout main && git pull origin main
git checkout -b feature/tool-best-deals

# save your file changes

git add agent/tools/seafood_prices.py agent/tools/__init__.py
git commit -m "feat: add get_best_deals tool for daily deal summary"
git push origin feature/tool-best-deals
# open Pull Request on GitHub
```

---

## How to verify it works

```bash
python -c "
from agent.tools.seafood_prices import get_best_deals

# All categories
print(get_best_deals.invoke({}))
print('---')
# Filter by fish
print(get_best_deals.invoke({'category': 'fish'}))
print('---')
# Invalid category
print(get_best_deals.invoke({'category': 'lobster'}))
"
```
