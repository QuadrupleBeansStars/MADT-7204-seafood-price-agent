# Task 02 — `get_price_trend` Tool

**Branch:** `feature/tool-price-trend`
**File to edit:** `agent/tools/seafood_prices.py` and `agent/tools/__init__.py`
**Difficulty:** Beginner (vibe code friendly)

---

## What you're building

A function that shows how the price of a seafood item has changed over the past N days across all shops. This helps users spot trends — is salmon getting cheaper or more expensive this week?

---

## How it fits into the system

```
User asks: "Has the price of salmon gone up this week?"
    │
    ▼
Agent (Gemini) decides to call: get_price_trend
    │  item = "salmon"
    │  days = 7
    ▼
Your tool looks up the last 7 days of salmon prices from the CSV
Returns a table: one row per date, columns = shops
    │
    ▼
Agent reads your output and replies:
"Salmon has increased ฿35/kg at Makro over the past 7 days (+12%).
 Or Tor Kor remained stable. Talad Thai is still the cheapest."
```

---

## What the function should do

- Accept an item name (e.g. `"salmon"`) and number of days (default 7)
- Look up the last N days of data from `data/raw/seafood_prices_sample.csv`
- Return a formatted table showing price per shop per date
- Include a summary: which shop had the biggest price change (% change from day 1 to last day)

---

## Vibe-code prompt

Copy this and paste it into Claude or Gemini:

```
I'm building a LangChain tool for a seafood price comparison agent.
The tool is called get_price_trend.

Here is the existing code in agent/tools/seafood_prices.py:
[paste the full file content here]

Please add a new @tool function with this signature:
get_price_trend(item: str, days: int = 7) -> str

- item: seafood item name (case-insensitive partial match against item_name column)
- days: number of past days to show (default 7, max 30)

Steps:
1. Load the CSV using the existing _load_prices() helper
2. Filter rows matching the item name
3. Take the last N unique dates
4. Return a table: rows = dates, columns = shop names, values = price_per_kg
5. Mark out-of-stock cells with "—" instead of a price
6. At the bottom, add a summary line per shop showing % change from oldest to newest date

Output example:
  Price trend for 'salmon' (last 7 days):

  Date         | Talad Thai | Or Tor Kor | Makro | ...
  2026-03-22   |  ฿320.0    |  ฿380.0   | ฿305.0| ...
  2026-03-23   |  ฿325.0    |  ฿378.0   | ฿310.0| ...
  ...

  7-day change:
    Talad Thai:  +฿15.0/kg (+4.7%)
    Or Tor Kor:  -฿2.0/kg  (-0.5%)
    Makro:       +฿25.0/kg (+8.2%)  ← biggest increase
```

---

## After generating the code

1. Paste the new function into `agent/tools/seafood_prices.py` (add at the bottom)
2. Open `agent/tools/__init__.py` and add `get_price_trend`:

```python
from agent.tools.seafood_prices import query_seafood_prices, get_price_trend

ALL_TOOLS = [query_seafood_prices, get_price_trend]
```

(Note: add alongside whatever other tools are already in `ALL_TOOLS`)

---

## Git steps

```bash
git checkout main && git pull origin main
git checkout -b feature/tool-price-trend

# paste your generated code, save files

git add agent/tools/seafood_prices.py agent/tools/__init__.py
git commit -m "feat: add get_price_trend tool for N-day price history"
git push origin feature/tool-price-trend
# open Pull Request on GitHub
```

---

## How to verify it works

```bash
python -c "
from agent.tools.seafood_prices import get_price_trend
print(get_price_trend.invoke({'item': 'salmon', 'days': 7}))
"
```

You should see a date × shop price table with a % change summary at the bottom.
