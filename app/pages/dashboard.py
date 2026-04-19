import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.loader import VALID_CATEGORIES, CATEGORY_TH, load_seafood_data

# --- Custom CSS ---
st.markdown("""
<style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .decision-box {
        background-color: #ffffff;
        border-left: 10px solid #1E3A8A;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 25px;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Loading ---
df = load_seafood_data()

if df is not None and not df.empty:
    st.title("🌊 Seafood Strategic Intelligence Hub")
    st.caption("Real-time price comparison across 7 Bangkok seafood shops")

    # --- Category filter ---
    cat_options = ["All"] + [f"{c} ({CATEGORY_TH[c]})" for c in sorted(VALID_CATEGORIES)]
    selected_cat = st.selectbox("Filter by category:", cat_options)

    if selected_cat != "All":
        cat_key = selected_cat.split(" (")[0]
        df_filtered = df[df["category"] == cat_key]
    else:
        df_filtered = df

    # Only rows with price_per_kg for fair comparison
    df_priced = df_filtered[df_filtered["price_per_kg"].notna()].copy()

    # --- 1. BIG DECISION CARD ---
    if not df_priced.empty:
        best_deal = df_priced.sort_values("price_per_kg").iloc[0]
        option_html = f"<br><span style='font-size:0.9rem;color:gray;'>Option: {best_deal['option']}</span>" if best_deal['option'] != '-' else ''
        link_html = f' <a href="{best_deal["link"]}" target="_blank">🔗 View product</a>' if best_deal['link'] else ''
        st.markdown(
            f'<div class="decision-box">'
            f'<h3 style="margin-top:0;color:#1E3A8A;">🎯 Best Deal Right Now</h3>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div>'
            f'<span style="font-size:1.8rem;font-weight:bold;">{best_deal["group_th"]} ({best_deal["group_en"]})</span><br>'
            f'<span style="font-size:1.1rem;">Shop: <b>{best_deal["source"]}</b></span>'
            f'{option_html}'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<span style="font-size:2.2rem;font-weight:bold;color:#28a745;">฿{best_deal["price_per_kg"]:,.0f}</span><br>'
            f'<span style="color:gray;">per kg</span>'
            f'</div>'
            f'</div>'
            f'<hr>'
            f'<p style="font-size:1rem;">✅ <b>Insight:</b> This item has the lowest price per kg across all shops.{link_html}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- 2. TOP INSIGHTS ---
    m1, m2, m3 = st.columns(3)

    if not df_priced.empty:
        cheapest = df_priced.sort_values("price_per_kg").iloc[0]
        m1.metric(
            "🥇 Cheapest Item",
            f"฿{cheapest['price_per_kg']:,.0f}/kg",
            f"{cheapest['group_th']} at {cheapest['source']}",
        )

        # Most expensive
        priciest = df_priced.sort_values("price_per_kg", ascending=False).iloc[0]
        m2.metric(
            "💎 Premium Item",
            f"฿{priciest['price_per_kg']:,.0f}/kg",
            f"{priciest['group_th']} at {priciest['source']}",
        )

        # Number of shops
        m3.metric("🏪 Shops Tracked", f"{df['source'].nunique()}", f"{len(df_priced)} items with price/kg")

    st.divider()

    # --- 3. PRICE COMPARISON BY GROUP ---
    st.subheader("📈 Price Comparison Across Shops")

    groups_with_data = sorted(df_priced["group_en"].unique())
    if groups_with_data:
        # Map to bilingual display
        group_display = {g: f"{df_priced[df_priced['group_en']==g].iloc[0]['group_th']} ({g})" for g in groups_with_data}
        selected_display = st.selectbox(
            "Select product group:",
            [group_display[g] for g in groups_with_data],
        )
        selected_group = [g for g, d in group_display.items() if d == selected_display][0]

        group_data = df_priced[df_priced["group_en"] == selected_group].copy()
        group_data["label"] = group_data.apply(
            lambda r: f"{r['source']}\n{r['option']}" if r["option"] != "-" else r["source"],
            axis=1,
        )

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

        col_insight1, col_insight2 = st.columns(2)
        col_insight1.metric("Lowest", f"฿{min_p:,.0f}/kg")
        col_insight2.metric("Price Spread", f"{spread_pct:.0f}%", f"฿{max_p - min_p:,.0f} range")

    st.divider()

    # --- 4. COMPARE MODE & CATALOG ---
    st.subheader("📋 Product Comparison & Catalog")

    sources = sorted(df_filtered["source"].unique())
    sel_sources = st.multiselect("Select shops to compare:", sources, default=sources[:2])

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
            st.markdown("**Side-by-Side Comparison (green = cheapest)**")
            st.dataframe(
                pivot.style.highlight_min(axis=1, color="#d4edda").format("฿{:,.0f}"),
                use_container_width=True,
            )

    st.markdown("---")

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
            "Link": st.column_config.LinkColumn("🔗 Link", display_text="View"),
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.error("No data found!")
