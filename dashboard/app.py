import streamlit as st
import sys
import os
import time
import datetime
import json
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# 🛠 PATH FIX: Ensures Streamlit can find project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.trade_logger import load_active_trades, load_closed_trades
from analytics.trade_analytics import compute_pair_stats

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="TRADEBOT_ICT | Console", 
    page_icon="📊", 
    layout="wide"
)

# 🔄 AUTO-REFRESH (Every 2 seconds)
st_autorefresh(interval=2000, key="datarefresh")

# --- 2. DATA LOADING & PROCESSING ---
active_trades = load_active_trades()
closed_trades = load_closed_trades()

# 🧠 STEP 1 — CALCULATE COUNTS
total_trades = len(active_trades) + len(closed_trades)
closed_count = len(closed_trades)
open_count = len(active_trades)

# 🧠 STEP 2 — TOTAL BALANCE (REAL)
if closed_trades:
    # Use the snapshot from the most recent closed trade
    current_balance = closed_trades[-1].get("balance_snapshot", 100)
else:
    current_balance = 100  # Starting fallback

# 🧠 STEP 3 — EQUITY CURVE CALCULATION
equity_data = []
running_balance = 100
for trade in closed_trades:
    pnl = trade.get("pnl", 0)
    running_balance += pnl
    equity_data.append(running_balance)

equity_df = pd.DataFrame({
    "Trade #": list(range(1, len(equity_data) + 1)),
    "Equity": equity_data
})

# --- 3. SIDEBAR & CONTROLS ---
st.sidebar.title("⚙️ CONTROL PANEL")

if st.sidebar.button("🗑 RESET ALL TRADES"):
    with open("storage/active_trades.json", "w") as f: f.write("[]")
    with open("storage/closed_trades.json", "w") as f: f.write("[]")
    with open("storage/trades.json", "w") as f: f.write("[]")
    st.sidebar.warning("Storage Cleared!")
    time.sleep(0.5)
    st.rerun()

st.sidebar.divider()
st.sidebar.success("Live Feed: ACTIVE")
refresh_time = time.strftime("%H:%M:%S")
st.sidebar.info(f"Last UI Update: {refresh_time}")

# --- 4. MAIN UI DISPLAY ---
st.title("📊 TRADEBOT PERFORMANCE DASHBOARD")

# 🧠 STEP 4 — DISPLAY METRICS
col1, col2, col3 = st.columns(3)
col1.metric("Total Trades", total_trades)
col2.metric("Open Trades", open_count)
col3.metric("Balance ($)", f"${round(current_balance, 2)}")

st.divider()

# --- 5. TABS INTERFACE ---
tab1, tab2, tab3 = st.tabs(["🎯 Active Exposure", "📜 History", "📈 Analytics"])

with tab1:
    st.subheader("Current Market Exposure")
    if active_trades:
        st.dataframe(active_trades, use_container_width=True)
    else:
        st.info("No active trades. Scanning for ICT setups...")

with tab2:
    st.subheader(f"Trade History ({closed_count})")
    if closed_trades:
        # Show most recent trades first in the history table
        st.dataframe(reversed(closed_trades), use_container_width=True)
    else:
        st.info("No closed trades found.")

with tab3:
    # 🧠 STEP 5 — EQUITY CHART
    st.subheader("📈 Equity Curve")
    if not equity_df.empty:
        st.line_chart(equity_df.set_index("Trade #"))
    else:
        st.info("No closed trades yet to plot equity.")

    if closed_trades:
        st.divider()
        pair_stats = compute_pair_stats(closed_trades)
        c_left, c_right = st.columns(2)
        
        with c_left:
            st.write("### Winrate per Asset")
            st.bar_chart({p: pair_stats[p]["winrate"] for p in pair_stats})
        
        with c_right:
            st.write("### Avg PnL per Asset")
            st.bar_chart({p: pair_stats[p]["avg_pnl"] for p in pair_stats})

# --- 6. DEVELOPER STATE ---
# 🧠 STEP 6 — FIX "DEVELOPER STATE"
with st.expander("🛠 Developer System State"):
    st.json({
        "last_refresh": refresh_time,
        "active_count": open_count,
        "closed_count": closed_count,
        "total_trades": total_trades,
        "balance": round(current_balance, 2)
    })