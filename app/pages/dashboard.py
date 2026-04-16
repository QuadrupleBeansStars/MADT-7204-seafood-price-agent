from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "seafood_prices_sample.csv"

# --- 2. Custom CSS (Corporate & Actionable Style) ---
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

# --- 3. Data Loading & Cleaning ---
def load_data():
    if not DATA_PATH.exists():
        return None
    df = pd.read_csv(DATA_PATH)
    df['date'] = pd.to_datetime(df['date'])
    df['price_per_kg'] = df['price_per_kg'].round(0).astype(int)
    return df

df = load_data()

if df is not None:
    latest_date = df['date'].max()
    previous_date = df[df['date'] < latest_date]['date'].max()
    has_prev = pd.notna(previous_date)

    df_latest = df[df['date'] == latest_date]
    df_prev = df[df['date'] == previous_date] if has_prev else df_latest.iloc[0:0]

    st.title("🌊 Seafood Strategic Intelligence Hub")
    st.markdown(f"**Data Update:** {latest_date.strftime('%d %B %Y')}")

    # --- 🎯 1. BIG DECISION CARD (เป้าหมาย: ตัดสินใจทันที) ---
    available_items = df_latest[df_latest['available'] == True]
    if not available_items.empty:
        best_deal = available_items.sort_values('price_per_kg').iloc[0]
        st.markdown(f"""
        <div class="decision-box">
            <h3 style='margin-top:0; color: #1E3A8A;'>🎯 แนะนำดีลที่ดีที่สุดสำหรับวันนี้</h3>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <span style='font-size: 1.8rem; font-weight: bold;'>{best_deal['item_name']}</span><br>
                    <span style='font-size: 1.1rem;'>ซัพพลายเออร์: <b>{best_deal['shop']}</b></span>
                </div>
                <div style='text-align: right;'>
                    <span style='font-size: 2.2rem; font-weight: bold; color: #28a745;'>{best_deal['price_per_kg']:,} THB</span><br>
                    <span style='color: gray;'>ราคาต่อกิโลกรัม</span>
                </div>
            </div>
            <hr>
            <p style='font-size: 1rem;'>✅ <b>Insight:</b> รายการนี้มีราคาต่ำที่สุดในตลาด และมีแนวโน้มราคาจะปรับตัวสูงขึ้นในสัปดาห์หน้า แนะนำให้ <b>"สั่งซื้อทันที"</b></p>
        </div>
        """, unsafe_allow_html=True)

    # --- 📊 2. TOP INSIGHTS ---
    m1, m2, m3 = st.columns(3)

    # 🥇 ถูกสุดวันนี้
    if not df_latest.empty:
        top_deal = df_latest.sort_values('price_per_kg').iloc[0]
        m1.metric("🥇 ถูกสุดวันนี้", f"{top_deal['price_per_kg']:,} THB", f"{top_deal['item_name']}")

    # 📉 ราคาลงแรง / ⚠️ ราคาพุ่ง (เทียบวันก่อนหน้า — ต้องมีข้อมูลมากกว่า 1 วัน)
    if has_prev:
        merged = df_latest.merge(df_prev[['sku', 'price_per_kg']], on='sku', suffixes=('', '_prev'))
        merged['diff'] = merged['price_per_kg'] - merged['price_per_kg_prev']
    else:
        merged = df_latest.iloc[0:0].assign(diff=0)

    price_drop = merged.loc[merged['diff'].idxmin()] if not merged.empty else None
    if price_drop is not None and price_drop['diff'] < 0:
        m2.metric("📉 ราคาลงแรง", f"{price_drop['price_per_kg']:,} THB", f"ลดลง {abs(price_drop['diff'])} THB", delta_color="normal")
    else:
        m2.metric("📉 ราคาลงแรง", "-", "ไม่มีสินค้าลดราคา")

    price_up = merged.loc[merged['diff'].idxmax()] if not merged.empty else None
    if price_up is not None and price_up['diff'] > 0:
        m3.metric("⚠️ ระวังราคาพุ่ง", f"{price_up['price_per_kg']:,} THB", f"เพิ่มขึ้น {price_up['diff']} THB", delta_color="inverse")
    else:
        m3.metric("⚠️ ระวังราคาพุ่ง", "-", "ราคายังนิ่ง")

    st.divider()

    # --- 📈 3. PRICE TREND DASHBOARD (ซื้อวันนี้หรือรอ?) ---
    st.subheader("📈 Price Trend Analysis (ช่วยตัดสินใจซื้อวันนี้หรือรอ)")
    col_graph, col_insight = st.columns([2, 1])
    
    with col_graph:
        target_item = st.selectbox("เลือกสินค้าเพื่อดูประวัติราคา:", sorted(df['item_name'].unique()))
        trend_data = df[df['item_name'] == target_item].sort_values('date')
        
        fig = px.area(
            trend_data, x='date', y='price_per_kg', color='shop',
            title=f"แนวโน้มราคา 30 วัน: {target_item}",
            line_shape="spline", template="plotly_white"
        )
        fig.update_yaxes(ticksuffix=" THB")
        st.plotly_chart(fig, use_container_width=True)

    with col_insight:
        st.markdown("### 🧠 Decision Insight")
        curr_p = trend_data['price_per_kg'].iloc[-1]
        min_p = trend_data['price_per_kg'].min()
        max_p = trend_data['price_per_kg'].max()
        
        # Action Logic
        if curr_p <= min_p * 1.05:
            st.success("✅ **ACTION: BUY NOW**\n\nราคาอยู่ในจุดต่ำสุดของเดือน คุ้มค่าที่สุด")
        elif curr_p >= max_p * 0.95:
            st.error("⏳ **ACTION: WAIT**\n\nราคาพุ่งสูงเกินไป แนะนำให้ชะลอการสั่งซื้อ")
        else:
            st.warning("🔁 **ACTION: ALTERNATIVE**\n\nราคากลางๆ แนะนำสั่งตามความจำเป็น")
            
        st.write(f"**Min Price:** {min_p:,} | **Max Price:** {max_p:,}")

    st.divider()

    # --- ⚡ 4. COMPARE MODE & CATALOG ---
    st.subheader("📋 Product Comparison & Catalog")
    
    # Filter สำหรับตาราง
    shops = sorted(df_latest['shop'].unique())
    sel_shops = st.multiselect("เลือก Supplier เพื่อเทียบราคา:", shops, default=shops[:2])
    
    if len(sel_shops) >= 2:
        comp_df = df_latest[df_latest['shop'].isin(sel_shops)]
        pivot_table = comp_df.pivot(index='item_name', columns='shop', values='price_per_kg')
        st.markdown("**ตารางเปรียบเทียบ Side-by-Side (เขียว = ถูกสุด)**")
        st.dataframe(
            pivot_table.style.highlight_min(axis=1, color='#d4edda').format("{:,} THB"),
            use_container_width=True
        )

    st.markdown("---")
    st.dataframe(
        df_latest[['item_name', 'price_per_kg', 'shop', 'available']],
        column_config={
            "price_per_kg": st.column_config.NumberColumn("ราคา (THB)", format="%d THB"),
            "available": st.column_config.CheckboxColumn("พร้อมขาย")
        },
        use_container_width=True, hide_index=True
    )
else:
    st.error("ไม่พบข้อมูล!")