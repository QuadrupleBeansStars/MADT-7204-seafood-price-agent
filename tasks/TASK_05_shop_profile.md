# Task 05 — Shop Profile Page

**Branch:** `feature/shop-profile-page`
**Files to create/edit:**
- Create: `app/pages/shop_profile.py`
- Edit: `app/main.py` (tab 3 — replace the placeholder)

---

## What you're building

A "shop report card" tab inside the Streamlit app. Users can explore individual shops — understanding their pricing patterns, what they carry, and how reliable their stock is.

This helps buyers build trust with a shop before committing to regular orders — it's not just about today's price, but consistency over time.

---

## How it fits into the system

```
User opens the web app → clicks "🏪 Shop Profiles" tab
    │
    ▼
Your Streamlit page loads
User picks a shop to explore
    │
    ▼
Page reads data/raw/seafood_prices_sample.csv directly using pandas
Shows stats, charts, and tables for the selected shop
```

No AI agent involved — this reads the CSV directly with pandas.

---

## What the page should include

Design the layout and content yourself. Think about what a buyer would want to know about a shop before deciding to source from them regularly.

At minimum, there should be a way to select a shop, and the page should display meaningful statistics and at least one visual (chart, metric, or table) about that shop's pricing and availability.

The data has these columns: `date`, `shop`, `sku`, `item_name`, `category`, `price_per_kg`, `unit`, `available`.

---

## Thinking steps

Before you start, think through what a buyer would want to know about a shop:

1. **What questions does a buyer ask about a supplier?** Think beyond just price — reliability, range of products, consistency over time.

2. **How do you compare a shop to the market?** You have prices from 5 shops. How do you calculate "market average" for a fair comparison?

3. **What does "availability rate" mean?** If a shop shows 90% availability, does that mean 90% of its items are in stock today, or across all 7 days of data?

4. **What's the most useful visual for this page?** A bar chart comparing this shop vs market average per item? A trend line showing how prices changed over the week? Think about what tells the clearest story.

5. **What if a shop carries different items on different days?** Your stats should handle the case where not every item appears every day.

6. **What's the data path?** Same as Task 4 — make sure the CSV path works when running from the repo root.

---

## Acceptance criteria

Your task is complete when:

- [ ] Running `streamlit run app/pages/shop_profile.py` from the repo root opens the page in a browser with no errors
- [ ] The page loads and displays content for the default selected shop
- [ ] Switching between shops updates all content correctly without crashing
- [ ] The page works for all 5 shops in the CSV
- [ ] No Python exceptions appear in the terminal while using the page normally

---

## After writing the code

1. Save the generated code to `app/pages/shop_profile.py`
2. You don't need to touch `app/main.py` — the IT Lead will wire the tab in after review.

---

## Git steps

```bash
git checkout main && git pull origin main
git checkout -b feature/shop-profile-page

# save your file to app/pages/shop_profile.py

git add app/pages/shop_profile.py
git commit -m "feat: add shop profile page"
git push origin feature/shop-profile-page
# open Pull Request on GitHub
```

---

## How to verify it works

```bash
streamlit run app/pages/shop_profile.py
```

Cycle through all 5 shops and confirm the page updates correctly each time with no errors.
