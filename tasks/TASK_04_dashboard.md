# Task 04 — Price Dashboard Page

**Branch:** `feature/dashboard-page`
**Files to create/edit:**
- Create: `app/pages/dashboard.py`
- Edit: `app/main.py` (tab 2 — replace the placeholder)

---

## What you're building

A visual price dashboard tab inside the Streamlit app. Users can filter and explore seafood prices visually — without typing anything to the AI agent.

This gives non-technical users (restaurant buyers, wholesalers) a quick way to browse the data before deciding what to order.

---

## How it fits into the system

```
User opens the web app → clicks "📊 Price Dashboard" tab
    │
    ▼
Your Streamlit page loads with filters in the sidebar
User picks what they want to explore
    │
    ▼
Page reads data/raw/seafood_prices_sample.csv directly using pandas
Updates charts and tables instantly
```

No AI agent involved — this reads the CSV directly with pandas.

---

## What the page should include

Design the sidebar filters and main content yourself. Think about what a restaurant buyer would want to explore when browsing seafood prices.

At minimum, the page needs at least one chart and at least one data table. What you put in the sidebar is up to you — think about which dimensions of the data are useful to filter on.

The data has these columns to work with: `date`, `shop`, `sku`, `item_name`, `category`, `price_per_kg`, `unit`, `available`.

---

## Thinking steps

Before you start, think through what a user would actually want to do on this page:

1. **Who is the user?** A restaurant buyer, a wholesaler, or a household trying to save money. What questions do they arrive with?

2. **What's the most useful first view?** When the page first loads, what should it show by default — today's prices? A summary? A specific item?

3. **What makes a chart useful here?** Think about what X and Y axes make sense for comparing seafood prices. Bar chart? Line chart? Both?

4. **What filters make the data manageable?** There are 16 items, 5 shops, 7 dates. Without filters, a table would have 560 rows. What combinations of filters are most natural?

5. **How do you show availability?** Out-of-stock items are important information. How do you make that visible without cluttering the chart?

6. **What's the data path?** The CSV is at `data/raw/seafood_prices_sample.csv`. When you run `streamlit run app/pages/dashboard.py` from the repo root, what is the working directory? Make sure the path works correctly.

---

## Acceptance criteria

Your task is complete when:

- [ ] Running `streamlit run app/pages/dashboard.py` from the repo root opens the page in a browser with no errors
- [ ] The page loads data from the CSV and displays it (chart and/or table visible on first load)
- [ ] Changing a filter updates the content without crashing
- [ ] The page works correctly across all combinations of filter values
- [ ] No Python exceptions appear in the terminal while using the page normally

---

## After writing the code

1. Save the generated code to `app/pages/dashboard.py`
2. You don't need to touch `app/main.py` — the IT Lead will wire the tab in after review.

---

## Git steps

```bash
git checkout main && git pull origin main
git checkout -b feature/dashboard-page

# save your file to app/pages/dashboard.py

git add app/pages/dashboard.py
git commit -m "feat: add price dashboard page"
git push origin feature/dashboard-page
# open Pull Request on GitHub
```

---

## How to verify it works

```bash
streamlit run app/pages/dashboard.py
```

Test by trying different filter combinations. Make sure nothing crashes when you select edge case values (e.g. an item that's out of stock everywhere on a selected date).
