import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.loader import load_seafood_data

# --- Custom Styling ---
st.markdown("""
<style>
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; }
    .shop-header { background-color: #1E3A8A; color: white; padding: 20px; border-radius: 15px; margin-bottom: 25px; }
</style>
""", unsafe_allow_html=True)

# --- Data Loading ---
df = load_seafood_data()

if df is None or df.empty:
    st.error("No data found!")
else:
    # Only rows with price_per_kg for comparisons
    df_priced = df[df["price_per_kg"].notna()].copy()

    # --- Sidebar: Shop Selection ---
    st.sidebar.title("🏪 Shop Profiles")
    all_shops = sorted(df["source"].unique())
    selected_shop = st.sidebar.selectbox("Select a shop:", all_shops)

    # Filter data for selected shop
    shop_df = df[df["source"] == selected_shop]
    shop_priced = shop_df[shop_df["price_per_kg"].notna()]

    # --- Header Area ---
    st.markdown(f"""
    <div class="shop-header">
        <h1 style='margin:0; color: white;'>🏪 {selected_shop}</h1>
        <p style='margin:0; opacity: 0.8;'>Product range and price positioning vs market</p>
    </div>
    """, unsafe_allow_html=True)

    # --- KPIs ---
    col1, col2, col3, col4 = st.columns(4)

    total_products = shop_df["group_en"].nunique()
    col1.metric("Product Groups", f"{total_products}")

    total_items = len(shop_df)
    col2.metric("Total Items (incl. options)", f"{total_items}")

    # Price vs market average
    if not shop_priced.empty:
        market_avg = df_priced.groupby("group_en")["price_per_kg"].mean()
        shop_avg = shop_priced.groupby("group_en")["price_per_kg"].mean()
        common_groups = shop_avg.index.intersection(market_avg.index)
        if len(common_groups) > 0:
            diffs = shop_avg[common_groups] - market_avg[common_groups]
            avg_diff = diffs.mean()
            col3.metric(
                "Avg vs Market",
                f"{'+'if avg_diff > 0 else ''}{avg_diff:,.0f} ฿/kg",
                delta_color="inverse",
            )
        else:
            col3.metric("Avg vs Market", "N/A")
    else:
        col3.metric("Avg vs Market", "N/A")

    # Categories covered
    cats = shop_df["category"].nunique()
    col4.metric("Categories", f"{cats}/5")

    st.divider()

    # --- ANALYSIS TABS ---
    tab1, tab2, tab3 = st.tabs(["📊 Price Positioning", "📦 Product Range", "📋 Full Catalog"])

    with tab1:
        st.subheader("Price vs Market Average")
        if not shop_priced.empty and len(common_groups) > 0:
            comparison = pd.DataFrame({
                "group_en": common_groups,
                "Shop Price (avg)": shop_avg[common_groups].values,
                "Market Average": market_avg[common_groups].values,
            })
            # Add Thai names
            group_th_map = df.drop_duplicates("group_en").set_index("group_en")["group_th"]
            comparison["label"] = comparison["group_en"].map(
                lambda g: f"{group_th_map.get(g, '')} ({g})"
            )

            fig_bar = px.bar(
                comparison,
                x="label",
                y=["Shop Price (avg)", "Market Average"],
                barmode="group",
                labels={"value": "Price (฿/kg)", "label": ""},
                color_discrete_map={
                    "Shop Price (avg)": "#1E3A8A",
                    "Market Average": "#E5E7EB",
                },
                template="plotly_white",
            )
            fig_bar.update_yaxes(ticksuffix=" ฿")
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Not enough per-kg price data for this shop to compare with market.")

    with tab2:
        st.subheader("Products by Category")
        cat_counts = shop_df.groupby(["category", "category_th"]).size().reset_index(name="count")
        cat_counts["label"] = cat_counts.apply(
            lambda r: f"{r['category_th']} ({r['category']})", axis=1
        )
        fig_pie = px.pie(
            cat_counts,
            values="count",
            names="label",
            title=f"Product distribution at {selected_shop}",
            template="plotly_white",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        # Price range per group
        if not shop_priced.empty:
            st.subheader("Price Range by Product Group")
            group_stats = shop_priced.groupby("group_en")["price_per_kg"].agg(["min", "max", "mean"]).reset_index()
            group_stats["group_th"] = group_stats["group_en"].map(
                df.drop_duplicates("group_en").set_index("group_en")["group_th"]
            )
            group_stats["label"] = group_stats.apply(
                lambda r: f"{r['group_th']} ({r['group_en']})", axis=1
            )
            fig_range = px.bar(
                group_stats.sort_values("mean"),
                x="label",
                y="mean",
                error_y=group_stats.sort_values("mean")["max"] - group_stats.sort_values("mean")["mean"],
                error_y_minus=group_stats.sort_values("mean")["mean"] - group_stats.sort_values("mean")["min"],
                labels={"mean": "Avg Price (฿/kg)", "label": ""},
                template="plotly_white",
            )
            fig_range.update_yaxes(ticksuffix=" ฿")
            st.plotly_chart(fig_range, use_container_width=True)

    with tab3:
        st.subheader("Full Product Catalog")
        catalog_cols = ["group_th", "group_en", "item_name_website", "option", "selling_price", "price_per_kg", "link"]
        available_cols = [c for c in catalog_cols if c in shop_df.columns]
        st.dataframe(
            shop_df[available_cols],
            column_config={
                "group_th": "ชื่อกลุ่ม",
                "group_en": "Group",
                "item_name_website": "Item Name",
                "option": "Option/Size",
                "selling_price": st.column_config.NumberColumn("Price (฿)", format="฿%,.0f"),
                "price_per_kg": st.column_config.NumberColumn("฿/kg", format="฿%,.0f"),
                "link": st.column_config.LinkColumn("🔗 Link", display_text="View"),
            },
            use_container_width=True,
            hide_index=True,
        )
