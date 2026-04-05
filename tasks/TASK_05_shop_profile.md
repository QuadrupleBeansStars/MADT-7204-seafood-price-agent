# Task 05 — Shop Profile Page

**Branch:** `feature/shop-profile-page`
**Files to create/edit:**
- Create: `app/pages/shop_profile.py`
- Edit: `app/main.py` (tab 3 — replace the placeholder)
**Difficulty:** Beginner (vibe code friendly — no agent knowledge needed)

---

## What you're building

A "shop report card" tab inside the Streamlit app. Users pick a shop and see its full profile: which items it carries, how its prices compare to the market average, and its availability rate.

This helps buyers evaluate which shop to trust for regular orders — not just on price, but on reliability.

---

## How it fits into the system

```
User opens the web app → clicks "🏪 Shop Profiles" tab
    │
    ▼
Your Streamlit page loads
User selects: shop = "Makro"
    │
    ▼
Page reads data/raw/seafood_prices_sample.csv directly
Shows: 16 items carried, avg price ฿245/kg vs market ฿278/kg (-12%)
Shows: 94% availability rate
Shows: table of all items with price vs market avg
```

No AI agent involved — this reads the CSV directly with Pandas.

---

## What the page should include

**Sidebar:**
- Dropdown: select shop (all 5 shop names from CSV)

**Main area:**
- Headline stats (3 columns):
  - Total items carried
  - Average price vs market average (with % above/below)
  - Availability rate (% of items in stock across all dates)
- Table: one row per item — item name, this shop's avg price, market avg price, % difference, typical availability
- A note at the bottom: "Based on sample data (seafood_prices_sample.csv)"

---

## Vibe-code prompt

Copy this and paste it into Claude or Gemini:

```
I'm building a Streamlit page for a seafood price comparison app.

The CSV file is at: data/raw/seafood_prices_sample.csv
Columns: date, shop, sku, item_name, category, price_per_kg, unit, available

Build a file called app/pages/shop_profile.py that:

1. Loads the CSV with pandas
2. Shows a sidebar selectbox to choose a shop (all unique shop names)
3. Filters data to the selected shop
4. Shows 3 metric cards at the top (use st.metric):
   - "Items Carried": count of unique item_names this shop has
   - "Avg Price vs Market": this shop's average price_per_kg vs the overall average across all shops (show % above or below)
   - "Availability Rate": percentage of rows where available=True for this shop
5. Shows a table with columns:
   - Item Name
   - This Shop Avg Price (฿/kg)
   - Market Avg Price (฿/kg)
   - Difference (% above or below market)
   - Availability (% of days in stock)
6. Use color to highlight: green if shop is cheaper than market, red if more expensive

Use st.set_page_config with title = "Shop Profiles" and layout = "wide".
```

---

## After generating the code

1. Save the generated code to `app/pages/shop_profile.py`
2. You don't need to edit `app/main.py` — the IT Lead will wire the tab in.

---

## Git steps

```bash
git checkout main && git pull origin main
git checkout -b feature/shop-profile-page

# save generated code to app/pages/shop_profile.py

git add app/pages/shop_profile.py
git commit -m "feat: add shop profile page with stats and price comparison table"
git push origin feature/shop-profile-page
# open Pull Request on GitHub
```

---

## How to verify it works

From the repo root (with conda env active):

```bash
streamlit run app/pages/shop_profile.py
```

A browser tab should open. Select different shops from the sidebar and confirm the metrics and table update correctly.
