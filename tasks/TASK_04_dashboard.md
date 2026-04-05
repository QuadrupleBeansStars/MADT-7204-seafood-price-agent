# Task 04 — Price Dashboard Page

**Branch:** `feature/dashboard-page`
**Files to create/edit:**
- Create: `app/pages/dashboard.py`
- Edit: `app/main.py` (tab 2 — replace the placeholder)
**Difficulty:** Beginner (vibe code friendly — no agent knowledge needed)

---

## What you're building

A visual price dashboard tab inside the Streamlit app. Users can filter by seafood item and date range, and see a bar chart comparing prices across all shops plus a full data table.

This gives non-technical users a visual way to explore prices without typing chat messages.

---

## How it fits into the system

```
User opens the web app → clicks "📊 Price Dashboard" tab
    │
    ▼
Your Streamlit page loads
User selects: item = "White Shrimp (Large)", date = "2026-03-28"
    │
    ▼
Page reads data/raw/seafood_prices_sample.csv directly
Draws a bar chart: X axis = shops, Y axis = price (฿/kg)
Shows a table below with all matching rows
Out-of-stock items highlighted in red
```

No AI agent involved — this reads the CSV directly with Pandas.

---

## What the page should include

**Sidebar:**
- Dropdown: select item (populated from CSV)
- Date picker or dropdown: select date (populated from CSV)

**Main area:**
- Bar chart: price per shop for the selected item + date (color-code availability)
- Data table: filtered rows (date, shop, item, price, available)
- A note: "Data source: seafood_prices_sample.csv"

---

## Vibe-code prompt

Copy this and paste it into Claude or Gemini:

```
I'm building a Streamlit page for a seafood price comparison app.

The CSV file is at: data/raw/seafood_prices_sample.csv
Columns: date, shop, sku, item_name, category, price_per_kg, unit, available

Build a file called app/pages/dashboard.py that:

1. Loads the CSV with pandas (relative path from repo root)
2. Shows a sidebar with:
   - A selectbox for item_name (all unique item names from CSV)
   - A selectbox for date (all unique dates from CSV, default = latest)
3. Filters the dataframe to the selected item + date
4. Shows a bar chart using st.bar_chart or plotly:
   - X axis = shop name
   - Y axis = price_per_kg
   - Color = green if available=True, red if available=False
5. Shows the filtered dataframe as a table below the chart
6. Shows a caption: "Data: seafood_prices_sample.csv (sample data)"

Use st.set_page_config to set title = "Price Dashboard" and layout = "wide".
```

---

## After generating the code

1. Save the generated code to `app/pages/dashboard.py`
2. Open `app/main.py` and replace the dashboard placeholder with:

```python
with tab_dashboard:
    from app.pages import dashboard  # noqa: F401
```

Or simply update the placeholder message to say "See dashboard.py" — the IT Lead will wire it in properly.

---

## Git steps

```bash
git checkout main && git pull origin main
git checkout -b feature/dashboard-page

# save generated code to app/pages/dashboard.py

git add app/pages/dashboard.py app/main.py
git commit -m "feat: add price dashboard page with bar chart and filter"
git push origin feature/dashboard-page
# open Pull Request on GitHub
```

---

## How to verify it works

From the repo root (with conda env active):

```bash
streamlit run app/pages/dashboard.py
```

A browser tab should open showing the sidebar filter and bar chart. Select different items and dates to make sure the chart updates.
