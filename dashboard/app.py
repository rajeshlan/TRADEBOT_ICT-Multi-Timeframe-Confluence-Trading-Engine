import streamlit as st
import sys
import os

# 🛠 PATH FIX: Ensures Streamlit can find 'analytics' and 'storage' modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.performance import get_stats

# --- Page Configuration ---
st.set_page_config(
    page_title="TRADEBOT_ICT | Performance", 
    page_icon="📊", 
    layout="wide"
)

# --- Custom Styling ---
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    [data-testid="stMetricValue"] {
        font-size: 28px;
        color: #00ffcc;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 TRADEBOT PERFORMANCE DASHBOARD")
st.caption("Real-time ICT Strategy Analytics & Kelly Criterion Tracking")

# Fetch data from the performance engine
stats = get_stats()

if not stats:
    st.info("🕒 **Waiting for data...** Once your first trade is closed by the Resolver, stats will appear here.")
    st.stop()

# --- Top Row: Core Trading Metrics ---
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Trades", stats["total"])
col2.metric("Wins ✅", stats["wins"])
col3.metric("Losses ❌", stats["losses"])
col4.metric("Win Rate", f"{stats['winrate']}%")

st.divider()

# --- Second Row: Financial Health ---
col5, col6, col7 = st.columns(3)

# Color the equity metric based on performance
equity_delta = round(stats['final_equity'] - 100, 2)
col5.metric("Final Equity", f"${stats['final_equity']}", f"{equity_delta}%")
col6.metric("Fixed RR", f"1:{stats['rr']}")
col7.metric("Net Return", f"{stats.get('total_return_pct', 0)}%")

st.divider()

# --- Visualization Section ---
st.subheader("📈 Equity Growth Curve")
st.line_chart(stats["equity_curve"])

# --- Raw Data Tooltip ---
with st.expander("See Raw Performance Data"):
    st.write(stats)

st.sidebar.success("Dashboard Connected")
st.sidebar.info(f"System Time: {os.popen('date').read()}")