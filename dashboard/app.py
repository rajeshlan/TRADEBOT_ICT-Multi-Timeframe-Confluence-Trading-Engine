import streamlit as st
import sys
import os
import time
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# --- 1. CLEAN COMPONENT IMPORTS ---
from components.styles import load_css
from components.metric_cards import render_metric_card
from components.position_cards import render_position_card
from components.history_cards import render_history_card
# Renamed import as requested
from components.live_feed import render_live_feed
from components.risk_panel import render_risk_panel
from components.charts import (
    render_equity_chart,
    render_winrate_chart
)
from components.order_cards import render_order_card

# --- 2. CORE SYSTEM IMPORTS ---
load_dotenv()

# This allows the app to find modules in the parent directory (core, storage, analytics)
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from storage.trade_logger import load_active_trades, load_closed_trades
from analytics.trade_analytics import compute_pair_stats
from core.executor import executor

# =========================================================
# PAGE CONFIG & THEME
# =========================================================
st.set_page_config(page_title="TRADEBOT_PRO", page_icon="📊", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)

# =========================================================
# DATA & REFRESH LOGIC
# =========================================================
st_autorefresh(interval=2000, key="refresh")

if "executor" not in st.session_state:
    st.session_state.executor = executor

@st.cache_data(ttl=5)
def get_balance_cached():
    try:
        return st.session_state.executor.get_balance()
    except Exception:
        return 0.0

# Fetch Data
live_positions = executor.get_all_positions()
closed_trades = load_closed_trades()
open_orders = executor.get_open_orders()
current_balance = get_balance_cached()

# Aggregations
floating_pnl = sum(float(p.get("unrealisedPnl", 0)) for p in live_positions)
equity_live = current_balance + floating_pnl
total_exposure = sum(abs(float(p.get("positionValue", 0))) for p in live_positions)
margin_ratio = (total_exposure / equity_live) if equity_live > 0 else 0
stats = compute_pair_stats(closed_trades)

# =========================================================
# HEADER & TOP KPI BAR
# =========================================================
st.title("📊 TRADEBOT_PRO | LIVE CONSOLE")

m_cols = st.columns(6)
metrics = [
    ("Equity", f"${equity_live:,.2f}"),
    ("Floating PnL", f"${floating_pnl:,.2f}"),
    ("Closed PnL", f"${sum(t.get('pnl', 0) for t in closed_trades):,.2f}"),
    ("Balance", f"${current_balance:,.2f}"),
    ("Open Positions", len([p for p in live_positions if abs(float(p.get("size", 0))) > 0])),
    ("Exposure", f"${total_exposure:,.2f}")
]

for col, (title, value) in zip(m_cols, metrics):
    with col:
        render_metric_card(title, value)

st.divider()

# =========================================================
# MAIN SPLIT LAYOUT (Command Center)
# =========================================================
left_col, right_col = st.columns([2, 1], gap="medium")

# --- LEFT COLUMN: TRADING OPS ---
with left_col:
    st.subheader("🎯 Active Market Exposure")
    if not live_positions:
        st.info("No active positions.")
    else:
        pos_grid = st.columns(2)
        for idx, p in enumerate(live_positions):
            with pos_grid[idx % 2]:
                render_position_card(p)

    st.markdown("---")
    st.subheader("⚡ Live Signal Feed")
    if closed_trades:
        # Renamed function usage here
        for t in list(reversed(closed_trades[-10:])):
            render_live_feed(t)

# --- RIGHT COLUMN: ANALYTICS & RISK ---
with right_col:
    st.subheader("📈 Performance Analytics")
    render_equity_chart(closed_trades)
    
    if stats:
        st.caption("Winrate by Asset")
        render_winrate_chart(stats)

    st.markdown("---")
    st.subheader("🛡️ Risk Management")
    render_risk_panel(margin_ratio)

    st.markdown("#### Open Orders")
    
    if open_orders:
        for o in open_orders:
            # Safety check: ensure 'o' is a dictionary before rendering
            if not isinstance(o, dict):
                continue
            render_order_card(o)
    else:
        st.caption("No pending orders.")

# =========================================================
# SIDEBAR SYSTEM STATUS
# =========================================================
st.sidebar.info(f"Last Sync: {time.strftime('%H:%M:%S')}")
if st.sidebar.button("Force Global Refresh"):
    st.cache_data.clear()
    st.rerun()