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
if "executor" not in st.session_state:
    st.session_state.executor = executor

# 4. CACHED API LOGIC
@st.cache_data(ttl=5)
def get_balance_cached():
    """Fetch balance from Bybit. Cached for 5s to prevent rate limits."""
    try:
        balance = st.session_state.executor.get_balance()
    except Exception as e:
        balance = 0
        print(f"⚠️ [DASHBOARD] Balance fetch failed: {e}")
    return balance

# 5. DATA LOADING
active_trades_json = load_active_trades()
closed_trades = load_closed_trades()

# ✅ LIVE EXCHANGE DATA (The Source of Truth)
live_positions = executor.get_all_positions()
open_orders = executor.get_open_orders()
current_balance = get_balance_cached() or 0.0

# ✅ CALCULATIONS
floating_pnl = round(sum(float(p.get("unrealisedPnl", 0)) for p in live_positions), 4)
closed_pnl = sum(t.get("pnl", 0) for t in closed_trades)
equity_live = current_balance + floating_pnl

# ✅ EXPOSURE & RISK CALCULATIONS
total_exposure = round(
    sum(abs(float(p.get("positionValue", 0))) for p in live_positions),
    2
)

margin_ratio = 0
if equity_live > 0:
    margin_ratio = total_exposure / equity_live

# ✅ DESYNC LOGIC
real_open_positions = len([
    p for p in live_positions
    if abs(float(p.get("size", 0))) > 0 or abs(float(p.get("unrealisedPnl", 0))) > 0
])
json_open_positions = len([
    t for t in active_trades_json
    if t.get("status") in ["PENDING", "OPEN", "ACTIVE"]
])

# 6. MAIN UI DISPLAY
st.title("📊 TRADEBOT PERFORMANCE DASHBOARD")

# --- WARNINGS SECTION ---
# A. Desync Warning
if json_open_positions != real_open_positions:
    st.warning(
        f"⚠️ STATE DESYNC | Local JSON: {json_open_positions} | Exchange Actual: {real_open_positions}"
    )

# B. Margin Exposure Warning
if margin_ratio >= 4:
    st.error(f"🚨 HIGH RISK EXPOSURE | Margin Ratio: {round(margin_ratio, 2)}x")
elif margin_ratio >= 2:
    st.warning(f"⚠️ Elevated Exposure | Margin Ratio: {round(margin_ratio, 2)}x")
else:
    st.success(f"✅ Exposure Healthy | Margin Ratio: {round(margin_ratio, 2)}x")


# --- TOP METRICS ROW ---
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Equity (USDT)", f"{round(equity_live, 2)}")
m2.metric("Floating PnL", f"{floating_pnl}", delta_color="normal")
m3.metric("Closed PnL", f"{round(closed_pnl, 4)}")
m4.metric("Balance (USDT)", f"{round(current_balance, 2)}")
m5.metric("Open Pos.", real_open_positions)
m6.metric("Exposure (USDT)", f"{total_exposure}")

st.divider()

# 7. SIDEBAR
st.sidebar.title("⚙️ CONTROL PANEL")
if st.sidebar.button("🗑 RESET ALL TRADES"):
    for file in ["active_trades.json", "closed_trades.json", "trades.json"]:
        file_path = f"storage/{file}"
        if os.path.exists(file_path):
            with open(file_path, "w") as f: f.write("[]")
    st.sidebar.warning("Storage Cleared!")
    time.sleep(0.5)
    st.rerun()

st.sidebar.divider()
st.sidebar.success("Live Engine: CONNECTED")
st.sidebar.info(f"Last UI Sync: {time.strftime('%H:%M:%S')}")

# 8. TABS INTERFACE
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Active Exposure", 
    "📋 Open Orders", 
    "📜 History", 
    "📈 Analytics"
])

with tab1:
    st.subheader("Live Market Exposure")
    if not live_positions:
        st.info("No active positions on exchange.")
    else:
        exposure_rows = []
        for p in live_positions:
            try:
                pnl = float(p.get("unrealisedPnl", 0))
                pos_val = float(p.get("positionValue", 1))
                roi = (pnl / pos_val) * 100 if pos_val > 0 else 0

                exposure_rows.append({
                    "Symbol": p.get("symbol"),
                    "Side": p.get("side"),
                    "Size": round(float(p.get("size", 0)), 4),
                    "Entry": round(float(p.get("avgPrice", 0)), 6),
                    "Mark": round(float(p.get("markPrice", 0)), 6),
                    "PnL": round(pnl, 4),
                    "ROI %": f"{round(roi, 2)}%",
                    "TP/SL": f"{p.get('takeProfit')} / {p.get('stopLoss')}",
                    "Lev": p.get("leverage")
                })
            except: continue
        
        # ✅ STYLED DATAFRAME
        df_exposure = pd.DataFrame(exposure_rows)

        def color_side(val):
            if str(val).lower() == "buy":
                return "color: #00ff88; font-weight: bold;"
            elif str(val).lower() == "sell":
                return "color: #ff4b4b; font-weight: bold;"
            return ""

        styled_df = df_exposure.style.map(color_side, subset=["Side"])

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True
        )

with tab2:
    st.subheader("Live TP/SL and Pending Orders")
    if not open_orders:
        st.info("No open orders found.")
    else:
        order_rows = []
        for o in open_orders:
            order_rows.append({
                "Symbol": o.get("symbol"),
                "Side": o.get("side"),
                "Type": o.get("orderType"),
                "Qty": o.get("qty"),
                "Price": o.get("price") if float(o.get("price", 0)) > 0 else "Market",
                "Trigger": o.get("triggerPrice") or "N/A",
                "Status": o.get("orderStatus")
            })
        st.dataframe(pd.DataFrame(order_rows), use_container_width=True, hide_index=True)

with tab3:
    st.subheader(f"Trade History ({len(closed_trades)})")
    if closed_trades:
        df_hist = pd.DataFrame(closed_trades).sort_values("closed_at", ascending=False)
        st.dataframe(df_hist[["symbol", "bias", "entry", "exit_price", "pnl", "result"]], use_container_width=True, hide_index=True)
    else:
        st.info("No history available.")

with tab4:
    st.subheader("📈 Performance Analytics")
    if closed_trades:
        # Simple Equity Chart
        curve = []
        bal = current_balance - closed_pnl
        for t in closed_trades:
            bal += t.get("pnl", 0)
            curve.append(bal)
        st.line_chart(pd.DataFrame({"Equity": curve}))
        
        # Stats
        pair_stats = compute_pair_stats(closed_trades)
        c1, c2 = st.columns(2)
        with c1: st.bar_chart({p: pair_stats[p]["winrate"] for p in pair_stats})
        with c2: st.bar_chart({p: pair_stats[p]["avg_pnl"] for p in pair_stats})

# 9. SYSTEM DEBUGGER
with st.expander("🛠 Developer System State"):
    st.json({
        "equity_live": equity_live,
        "api_balance": current_balance,
        "active_json_count": json_open_positions,
        "exchange_pos_count": real_open_positions,
        "open_orders_count": len(open_orders),
        "margin_ratio": margin_ratio,
        "desync": json_open_positions != real_open_positions
    })