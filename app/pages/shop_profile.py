from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "seafood_prices_sample.csv"

# --- 1. Page Configuration ---
st.set_page_config(page_title="Shop Profile Report", layout="wide")

# --- 2. Custom Styling ---
st.markdown("""
<style>
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; }
    .shop-header { background-color: #1E3A8A; color: white; padding: 20px; border-radius: 15px; margin-bottom: 25px; }
</style>
""", unsafe_allow_html=True)

# --- 3. Data Loading ---
def load_data():
    if not DATA_PATH.exists():
        return None
    df = pd.read_csv(DATA_PATH)
    df['date'] = pd.to_datetime(df['date'])
    df['price_per_kg'] = df['price_per_kg'].round(0).astype(int)
    return df

df = load_data()

if df is None:
    st.error(f"❌ ไม่พบไฟล์ข้อมูลที่ {DATA_PATH}")
else:
    # --- 4. Sidebar: Shop Selection ---
    st.sidebar.title("🏪 Shop Profiles")
    all_shops = sorted(df['shop'].unique())
    selected_shop = st.sidebar.selectbox("เลือกซัพพลายเออร์:", all_shops)

    # กรองข้อมูล
    shop_df = df[df['shop'] == selected_shop]
    latest_date = shop_df['date'].max()
    shop_latest = shop_df[shop_df['date'] == latest_date]

    # --- 5. Header Area ---
    st.markdown(f"""
    <div class="shop-header">
        <h1 style='margin:0; color: white;'>🏪 {selected_shop}</h1>
        <p style='margin:0; opacity: 0.8;'>วิเคราะห์ประสิทธิภาพและระดับราคาเปรียบเทียบกับตลาด</p>
    </div>
    """, unsafe_allow_html=True)

    # --- 6. SHOP REPORT CARD (KPIs) ---
    col1, col2, col3, col4 = st.columns(4)
    
    total_skus = shop_latest['item_name'].nunique()
    col1.metric("สินค้าทั้งหมด", f"{total_skus} รายการ")

    availability_rate = (shop_df['available'].sum() / len(shop_df)) * 100
    col2.metric("ความแม่นยำสต็อก", f"{availability_rate:.0f}%")

    # คำนวณราคาเทียบตลาด
    market_avg_today = df[df['date'] == latest_date].groupby('item_name')['price_per_kg'].mean()
    shop_prices = shop_latest.set_index('item_name')['price_per_kg']
    # หาค่าเฉลี่ยส่วนต่าง
    diffs = shop_prices - market_avg_today
    avg_diff = diffs.mean()
    
    col3.metric("ราคาเทียบตลาดเฉลี่ย", 
                f"{'+' if avg_diff > 0 else ''}{int(avg_diff)} THB", 
                delta_color="inverse")

    col4.metric("ข้อมูลล่าสุดเมื่อ", latest_date.strftime('%d %b'))

    st.divider()

    # --- 7. ANALYSIS TABS ---
    tab1, tab2, tab3 = st.tabs(["📊 Price Positioning", "📈 Price History", "📋 Inventory Detail"])

    with tab1:
        st.subheader("Price vs Market Average (Today)")
        comparison_df = shop_latest[['item_name', 'price_per_kg']].copy()
        comparison_df['Market Average'] = comparison_df['item_name'].map(market_avg_today.to_dict())
        
        fig_bar = px.bar(
            comparison_df, x='item_name', y=['price_per_kg', 'Market Average'],
            barmode='group',
            labels={'value': 'ราคา (THB)', 'item_name': 'สินค้า'},
            color_discrete_map={'price_per_kg': '#1E3A8A', 'Market Average': '#E5E7EB'}
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with tab2:
        st.subheader("ประวัติราคาสินค้าในร้านนี้")
        target_item = st.selectbox("เลือกสินค้า:", sorted(shop_df['item_name'].unique()))
        item_trend = shop_df[shop_df['item_name'] == target_item].sort_values('date')
        
        fig_line = px.line(
            item_trend, x='date', y='price_per_kg',
            markers=True, line_shape="spline"
        )
        fig_line.update_yaxes(ticksuffix=" THB")
        st.plotly_chart(fig_line, use_container_width=True)

    with tab3:
        st.subheader("รายการสต็อกปัจจุบัน")
        st.dataframe(
            shop_latest[['item_name', 'category', 'price_per_kg', 'available']],
            column_config={
                "price_per_kg": st.column_config.NumberColumn("ราคา", format="%d THB"),
                "available": st.column_config.CheckboxColumn("พร้อมส่ง")
            },
            use_container_width=True, hide_index=True
        )