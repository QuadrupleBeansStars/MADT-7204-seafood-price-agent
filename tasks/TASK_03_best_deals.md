# Task 03 — `get_best_deals` Tool

**Branch:** `feature/tool-best-deals`
**File to edit:** `agent/tools/seafood_prices.py` and `agent/tools/__init__.py`
**Difficulty:** Beginner (vibe code friendly)

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

## Vibe-code prompt

Copy this and paste it into Claude or Gemini:

```
I'm building a LangChain tool for a seafood price comparison agent.
The tool is called get_best_deals.

Here is the existing code in agent/tools/seafood_prices.py:
[paste the full file content here]

Please add a new @tool function with this signature:
get_best_deals(category: str | None = None, target_date: str | None = None) -> str

- category: optional filter — "fish", "shrimp", "squid", "crab", or "shellfish"
- target_date: optional YYYY-MM-DD, defaults to latest date in CSV

Steps:
1. Load the CSV using _load_prices()
2. Filter to the target date (latest if not specified)
3. Filter to available items only
4. If category is provided, filter by the category column
5. For each item_name, calculate the average price across all shops
6. Find shops where price < (average * 0.90) — i.e. more than 10% below average
7. Rank these "deals" by % discount (largest first)
8. Return formatted output

Output example:
  Best deals today (2026-03-28):

  🏆 #1  White Shrimp (Large)
         Talad Thai: ฿252/kg  |  Market avg: ฿308/kg  |  18% BELOW AVERAGE

  🥈 #2  Tilapia
         Makro: ฿96/kg  |  Market avg: ฿109/kg  |  12% BELOW AVERAGE

  If no deals found, return: "No significant deals today — prices are close to average across all shops."
```

---

## After generating the code

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

# paste your generated code, save files

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
print(get_best_deals.invoke({}))
print('---')
print(get_best_deals.invoke({'category': 'fish'}))
"
```

You should see a ranked list of deals for all items, then filtered to fish only.
