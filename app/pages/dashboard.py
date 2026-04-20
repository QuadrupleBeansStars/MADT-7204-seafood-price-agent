import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.loader import VALID_CATEGORIES, CATEGORY_TH, load_seafood_data


@st.cache_data(ttl="5m")
def _load_data():
    return load_seafood_data()


# --- Data Loading ---
df = _load_data()

if df is not None and not df.empty:
    st.title("Seafood price dashboard")
    st.caption("Real-time price comparison across 7 Bangkok seafood shops")

    # --- Category filter in sidebar ---
    with st.sidebar:
        cat_options = ["All"] + [f"{c} ({CATEGORY_TH[c]})" for c in sorted(VALID_CATEGORIES)]
        selected_cat = st.selectbox("Filter by category", cat_options)

    if selected_cat != "All":
        cat_key = selected_cat.split(" (")[0]
        df_filtered = df[df["category"] == cat_key]
    else:
        df_filtered = df

    # Only rows with price_per_kg for fair comparison
    df_priced = df_filtered[df_filtered["price_per_kg"].notna()].copy()

    # --- 1. BEST DEAL CARD ---
    if not df_priced.empty:
        best_deal = df_priced.sort_values("price_per_kg").iloc[0]
        with st.container(border=True):
            st.subheader("Best deal right now", divider="blue")
            deal_cols = st.columns([3, 1])
            with deal_cols[0]:
                st.markdown(f"**{best_deal['group_th']} ({best_deal['group_en']})**")
                st.caption(f"Shop: {best_deal['source']}"
                           + (f" | Option: {best_deal['option']}" if best_deal['option'] != '-' else ''))
                if best_deal['link']:
                    st.markdown(f"[View product]({best_deal['link']})")
            with deal_cols[1]:
                st.metric("Price", f"฿{best_deal['price_per_kg']:,.0f}/kg", border=True)

    # --- 2. TOP INSIGHTS ---
    if not df_priced.empty:
        cheapest = df_priced.sort_values("price_per_kg").iloc[0]
        priciest = df_priced.sort_values("price_per_kg", ascending=False).iloc[0]

        with st.container(horizontal=True):
            st.metric(
                "Cheapest item",
                f"฿{cheapest['price_per_kg']:,.0f}/kg",
                f"{cheapest['group_th']} at {cheapest['source']}",
                border=True,
            )
            st.metric(
                "Premium item",
                f"฿{priciest['price_per_kg']:,.0f}/kg",
                f"{priciest['group_th']} at {priciest['source']}",
                border=True,
            )
            st.metric(
                "Shops tracked",
                f"{df['source'].nunique()}",
                f"{len(df_priced)} items with price/kg",
                border=True,
            )

    # --- 3. PRICE COMPARISON BY GROUP ---
    st.subheader("Price comparison across shops")

    groups_with_data = sorted(df_priced["group_en"].unique())
    if groups_with_data:
        # Map to bilingual display
        group_display = {g: f"{df_priced[df_priced['group_en']==g].iloc[0]['group_th']} ({g})" for g in groups_with_data}
        selected_display = st.selectbox(
            "Select product group",
            [group_display[g] for g in groups_with_data],
        )
        selected_group = [g for g, d in group_display.items() if d == selected_display][0]

        group_data = df_priced[df_priced["group_en"] == selected_group].copy()
        group_data["label"] = group_data.apply(
            lambda r: f"{r['source']}\n{r['option']}" if r["option"] != "-" else r["source"],
            axis=1,
        )

        with st.container(border=True):
            fig = px.bar(
                group_data.sort_values("price_per_kg"),
                x="label",
                y="price_per_kg",
                color="source",
                title=f"Price per kg: {selected_display}",
                labels={"price_per_kg": "Price (฿/kg)", "label": ""},
                template="plotly_white",
            )
            fig.update_yaxes(ticksuffix=" ฿")
            st.plotly_chart(fig, use_container_width=True)

        # Action insight
        prices = group_data["price_per_kg"]
        min_p, max_p = prices.min(), prices.max()
        spread_pct = ((max_p - min_p) / min_p * 100) if min_p > 0 else 0

        with st.container(horizontal=True):
            st.metric("Lowest", f"฿{min_p:,.0f}/kg", border=True)
            st.metric("Price spread", f"{spread_pct:.0f}%", f"฿{max_p - min_p:,.0f} range", border=True)

    # --- 4. COMPARE MODE & CATALOG ---
    st.subheader("Product comparison & catalog")

    sources = sorted(df_filtered["source"].unique())
    sel_sources = st.multiselect("Select shops to compare", sources, default=sources[:2])

    if len(sel_sources) >= 2:
        # Pivot: group_en × source, showing min price_per_kg per cell
        comp_df = df_priced[df_priced["source"].isin(sel_sources)]
        pivot = comp_df.pivot_table(
            index="group_en",
            columns="source",
            values="price_per_kg",
            aggfunc="min",
        )
        if not pivot.empty:
            with st.container(border=True):
                st.caption("Side-by-side comparison (green = cheapest)")
                st.dataframe(
                    pivot.style.highlight_min(axis=1, color="#d4edda").format("฿{:,.0f}"),
                    use_container_width=True,
                )

    # Full catalog
    catalog_cols = ["group_th", "group_en", "source", "option", "price_per_kg", "selling_price", "link"]
    catalog = df_filtered[catalog_cols].copy()
    catalog = catalog.rename(columns={
        "group_th": "ชื่อสินค้า",
        "group_en": "Product",
        "source": "Shop",
        "option": "Option",
        "price_per_kg": "฿/kg",
        "selling_price": "Price (pack)",
        "link": "Link",
    })
    st.dataframe(
        catalog,
        column_config={
            "฿/kg": st.column_config.NumberColumn(format="฿%,.0f"),
            "Price (pack)": st.column_config.NumberColumn(format="฿%,.0f"),
            "Link": st.column_config.LinkColumn("Link", display_text="View"),
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.error("No data found!")
