import streamlit as st
import sys
import os
import time
import pandas as pd
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# 1. PATH & ENV SETUP
load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.trade_logger import load_active_trades, load_closed_trades
from analytics.trade_analytics import compute_pair_stats

# ✅ SHARED EXECUTOR: Using the global singleton instance
from core.executor import executor

# 2. CONFIGURATION
st.set_page_config(
    page_title="TRADEBOT_PRO | Console", 
    page_icon="📊", 
    layout="wide"
)

# 🔄 AUTO-REFRESH: Every 2 seconds to keep data live
st_autorefresh(interval=2000, key="datarefresh")

# 3. INITIALIZE EXECUTOR IN SESSION STATE
# This ensures Streamlit uses the shared connection across all UI refreshes.
if "executor" not in st.session_state:
    st.session_state.executor = executor

# 4. CACHED API LOGIC (REFACTORED)
# ttl=5 ensures we only hit the real API once every 5 seconds maximum.
@st.cache_data(ttl=5)
def get_balance_cached():
    """
    Fetch balance from Bybit through the executor. 
    Results are cached for 5 seconds to prevent rate limiting.
    Includes a safety wrapper to prevent UI crashes during API downtime.
    """
    try:
        # ✅ FIXED: Safe wrapper for API calls
        balance = st.session_state.executor.get_balance()
    except Exception as e:
        # Fallback to 0 if the API call fails
        balance = 0
        print(f"⚠️ [DASHBOARD] Balance fetch failed: {e}")
        
    return balance

# 5. DATA LOADING & CALCULATIONS
active_trades = load_active_trades()
closed_trades = load_closed_trades()

# Handle Balance with Cache
current_balance = get_balance_cached()

# Safety Fallback: Use 0.0 if balance retrieval failed or returned None
if current_balance is None:
    current_balance = 0.0

floating_pnl = sum(t.get("unrealized_pnl", 0) for t in active_trades)
closed_pnl = sum(t.get("pnl", 0) for t in closed_trades)
equity_live = current_balance + floating_pnl

# 6. SIDEBAR & CONTROLS
st.sidebar.title("⚙️ CONTROL PANEL")
if st.sidebar.button("🗑 RESET ALL TRADES"):
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

# 7. MAIN UI DISPLAY
st.title("📊 TRADEBOT PERFORMANCE DASHBOARD")

# Metrics Display
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Equity (USDT)", f"{round(equity_live, 2)}")
m2.metric("Floating PnL", f"{round(floating_pnl, 4)}", delta_color="normal")
m3.metric("Closed PnL", f"{round(closed_pnl, 4)}")
m4.metric("Balance (USDT)", f"{round(current_balance, 2)}")
m5.metric("Open Pos.", len(active_trades))

st.divider()

# 8. TABS INTERFACE
tab1, tab2, tab3 = st.tabs(["🎯 Active Exposure", "📜 History", "📈 Analytics"])

with tab1:
    st.subheader("Current Market Exposure")
    if active_trades:
        df_active = pd.DataFrame(active_trades)
        df_active["realized_pnl"] = 0.0
        cols = ["symbol", "bias", "entry", "status", "unrealized_pnl", "unrealized_pct", "realized_pnl"]
        st.dataframe(df_active[cols], use_container_width=True)
    else:
        st.info("No active trades. Scanning setups...")

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
    
    # Simple Equity Curve Generation
    equity_curve = []
    temp_balance = current_balance - closed_pnl
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

# 9. DEVELOPER DEBUGGER
with st.expander("🛠 Developer System State"):
    st.json({
        "equity_live": equity_live,
        "api_balance": current_balance,
        "cache_status": "Active (5s TTL)",
        "env_check": "API KEY FOUND" if os.getenv("BYBIT_API_KEY") else "API KEY MISSING"
    })