# Task 02 — `get_price_trend` Tool

**Branch:** `feature/tool-price-trend`
**File to edit:** `agent/tools/seafood_prices.py` and `agent/tools/__init__.py`

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

## Thinking steps

Before you ask an AI to write the code, think through these questions:

1. **How do you find "the last N days"?** The CSV has a `date` column. How do you get the N most recent unique dates? What if N is larger than the number of dates in the CSV?

2. **How should the table be structured?** Rows = dates, columns = shops — or the other way around? Which is easier to read?

3. **What if the item name doesn't match anything?** The user types `"tuna"` but the CSV only has `"Atlantic Salmon"`, `"Sea Bass"`, etc. What should the function return?

4. **What if `days` isn't a valid number?** The agent might pass it as an integer, but what if somehow it comes in as `"seven"` or `"-3"`? Think about what a safe fallback looks like.

5. **What about out-of-stock entries?** If a shop had no stock on a certain day, should that show as `฿0`, `"—"`, or be left blank in the table?

6. **How do you show the % change summary?** You need the first and last price for each shop. What if a shop was out of stock on the first or last day — can you still calculate a change?

---

## Acceptance criteria

Your task is complete when all of the following work correctly:

**Basic cases:**
- [ ] Valid item name, default 7 days → returns a date × shop price table with a % change summary
- [ ] Valid item name, custom days (e.g. `days=3`) → shows only the last 3 days
- [ ] Item name matched case-insensitively and partially (e.g. `"shrimp"` matches `"White Shrimp (Large)"`)

**Edge cases:**
- [ ] Item name not found → returns a clear error message, suggests checking available items or categories
- [ ] `days` is larger than the number of dates in the CSV → returns all available dates, doesn't crash
- [ ] `days` is 0 or negative → returns a friendly error message (e.g. `"days must be a positive number"`)
- [ ] `days` is passed as a non-integer (e.g. a float like `7.5`) → either rounds it or returns a clear error
- [ ] Some shops are out of stock on certain dates → shown clearly in the table (e.g. `"—"` or `"N/A"`), doesn't break the % change calculation

**Output quality:**
- [ ] Summary line shows which shop had the biggest price increase and which had the biggest decrease
- [ ] Output clearly states the date range covered

---

## After writing the code

1. Paste the new function into `agent/tools/seafood_prices.py` (add at the bottom)
2. Open `agent/tools/__init__.py` and add `get_price_trend`:

```python
from agent.tools.seafood_prices import query_seafood_prices, get_price_trend

ALL_TOOLS = [query_seafood_prices, get_price_trend]
```

(Add alongside whatever other tools are already in `ALL_TOOLS`)

---

## Git steps

```bash
git checkout main && git pull origin main
git checkout -b feature/tool-price-trend

# save your file changes

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

# Basic: 7-day trend
print(get_price_trend.invoke({'item': 'salmon', 'days': 7}))
print('---')
# Partial match
print(get_price_trend.invoke({'item': 'shrimp', 'days': 3}))
print('---')
# Item not found
print(get_price_trend.invoke({'item': 'tuna', 'days': 7}))
print('---')
# days = 0 (edge case)
print(get_price_trend.invoke({'item': 'salmon', 'days': 0}))
print('---')
# days larger than data
print(get_price_trend.invoke({'item': 'salmon', 'days': 999}))
"
```
