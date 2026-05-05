import streamlit as st
import sys
import os
import time
import pandas as pd
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# ✅ CRITICAL: Load environment variables before anything else
# This ensures that the Bybit API keys are available to the core modules.
load_dotenv()

# 🛠 PATH FIX: Ensures Streamlit can find project modules (storage, core, analytics)
# We calculate the root path relative to this script's location.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.trade_logger import load_active_trades, load_closed_trades
from analytics.trade_analytics import compute_pair_stats
from core.account import get_live_balance

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="TRADEBOT_PRO | Console", 
    page_icon="📊", 
    layout="wide"
)

# 🔄 AUTO-REFRESH
# Keeps the dashboard alive and updating every 2 seconds.
st_autorefresh(interval=2000, key="datarefresh")

# --- 2. DATA LOADING ---
active_trades = load_active_trades()
closed_trades = load_closed_trades()

# --- 3. PNL & EQUITY CALCULATIONS ---
# Summing up current floating PnL from active positions stored in active_trades.json
floating_pnl = sum(t.get("unrealized_pnl", 0) for t in active_trades)
closed_pnl = sum(t.get("pnl", 0) for t in closed_trades)

# ✅ LIVE BALANCE INTEGRATION
# This calls the hardened BybitExecutor we refined in previous steps.
current_balance = get_live_balance()

# Safety Fallback: If API fails or keys are missing, default to 0 to prevent UI crash.
if current_balance is None:
    current_balance = 0.0

# Total Equity = Current Wallet Balance (Live) + Unrealized Profits/Losses (Floating)
equity_live = current_balance + floating_pnl

# --- 4. SIDEBAR & CONTROLS ---
st.sidebar.title("⚙️ CONTROL PANEL")
if st.sidebar.button("🗑 RESET ALL TRADES"):
    # Safety: Clears local storage for a fresh testing session.
    for file in ["active_trades.json", "closed_trades.json", "trades.json"]:
        file_path = f"storage/{file}"
        if os.path.exists(file_path):
            with open(file_path, "w") as f: 
                f.write("[]")
    st.sidebar.warning("Storage Cleared!")
    time.sleep(0.5)
    st.rerun()

st.sidebar.divider()
st.sidebar.success("Live Engine: CONNECTED")
st.sidebar.info(f"Last UI Sync: {time.strftime('%H:%M:%S')}")

# --- 5. MAIN UI DISPLAY ---
st.title("📊 TRADEBOT PERFORMANCE DASHBOARD")

# ✅ DETAILED METRICS DISPLAY
# These metrics provide the high-level health of your account.
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Equity ($)", f"${round(equity_live, 2)}")
m2.metric("Floating PnL", f"${round(floating_pnl, 4)}", delta_color="normal")
m3.metric("Closed PnL", f"${round(closed_pnl, 4)}")
m4.metric("Balance ($)", f"${round(current_balance, 2)}")
m5.metric("Open Pos.", len(active_trades))

st.divider()

# --- 6. TABS INTERFACE ---
tab1, tab2, tab3 = st.tabs(["🎯 Active Exposure", "📜 History", "📈 Analytics"])

with tab1:
    st.subheader("Current Market Exposure")
    if active_trades:
        df_active = pd.DataFrame(active_trades)
        df_active["realized_pnl"] = 0.0
        cols = ["symbol", "bias", "entry", "status", "unrealized_pnl", "unrealized_pct", "realized_pnl"]
        st.dataframe(df_active[cols], use_container_width=True)
    else:
        st.info("No active trades. Scanning for high-quality setups...")

with tab2:
    st.subheader(f"Trade History ({len(closed_trades)})")
    if closed_trades:
        df_closed = pd.DataFrame(closed_trades)
        if not df_closed.empty:
            df_closed = df_closed.sort_values("closed_at", ascending=False)
            req_cols = ["symbol", "bias", "entry", "exit_price", "pnl", "pnl_pct", "result"]
            display_cols = [c for c in req_cols if c in df_closed.columns]
            st.dataframe(df_closed[display_cols], use_container_width=True)
    else:
        st.info("No closed trades found.")

with tab3:
    st.subheader("📈 Performance Analytics")
    
    equity_curve = []
    temp_balance = current_balance - closed_pnl # Reverse engineering start point
    for t in closed_trades:
        temp_balance += t.get("pnl", 0)
        equity_curve.append(temp_balance)
    
    if equity_curve:
        st.line_chart(pd.DataFrame({"Equity": equity_curve}))
    
    if closed_trades:
        st.divider()
        pair_stats = compute_pair_stats(closed_trades)
        c1, c2 = st.columns(2)
        with c1:
            st.write("### Winrate per Asset")
            st.bar_chart({p: pair_stats[p]["winrate"] for p in pair_stats})
        with c2:
            st.write("### Avg PnL per Asset")
            st.bar_chart({p: pair_stats[p]["avg_pnl"] for p in pair_stats})

# --- 7. DEVELOPER DEBUGGER ---
with st.expander("🛠 Developer System State"):
    st.json({
        "equity_live": equity_live,
        "floating_pnl": floating_pnl,
        "closed_pnl": closed_pnl,
        "active_count": len(active_trades),
        "history_count": len(closed_trades),
        "api_balance": current_balance,
        "env_check": "API KEY FOUND" if os.getenv("BYBIT_API_KEY") else "API KEY MISSING"
    })