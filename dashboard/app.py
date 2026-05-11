import streamlit as st
import sys
import os
import time
import pandas as pd
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# =========================================================
# PATH + ENV
# =========================================================

load_dotenv()

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from storage.trade_logger import (
    load_active_trades,
    load_closed_trades
)

from analytics.trade_analytics import compute_pair_stats

from core.executor import executor

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="TRADEBOT_PRO",
    page_icon="📊",
    layout="wide"
)

# =========================================================
# DARK THEME CSS
# =========================================================

st.markdown("""
<style>

html, body, [class*="css"]  {
    background-color: #0e1117;
    color: #fafafa;
}

.metric-card {
    background: rgba(20,20,25,0.96);
    padding: 18px;
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 0 20px rgba(0,0,0,0.4);
    margin-bottom: 16px;
}

.glow {
    box-shadow: 0 0 18px rgba(0,255,153,0.15);
}

.green {
    color: #00ff99;
    font-weight: bold;
}

.red {
    color: #ff4b4b;
    font-weight: bold;
}

.metric-title {
    font-size: 13px;
    opacity: 0.7;
    margin-bottom: 4px;
}

.metric-value {
    font-size: 26px;
    font-weight: bold;
}

.feed-card {
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 8px;
    border-left: 4px solid #00ff99;
}

.small-text {
    font-size: 13px;
    opacity: 0.8;
}

hr {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.08);
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# UI COMPONENTS
# =========================================================

def render_metric_card(title, value):
    st.markdown(f"""
    <div class="metric-card glow">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def render_position_card(position):
    pnl = float(position.get("unrealisedPnl", 0))
    pos_val = abs(float(position.get("positionValue", 1)))
    
    roi = ((pnl / pos_val) * 100 if pos_val > 0 else 0)
    roi = max(min(roi, 100), -100)

    pnl_class = "green" if pnl >= 0 else "red"
    side = position.get("side")
    side_color = "#00ff99" if str(side).lower() == "buy" else "#ff4b4b"

    st.markdown(f"""
    <div class="metric-card glow">
        <h3>{position.get("symbol")}</h3>
        <p>
            Side:
            <span style="color:{side_color}; font-weight:bold;">{side}</span>
        </p>
        <p>Entry: {position.get("avgPrice")}</p>
        <p>Mark: {position.get("markPrice")}</p>
        <p class="{pnl_class}">PnL: {round(pnl, 4)}</p>
        <p>ROI: {round(roi, 2)}%</p>
        <p class="small-text">
            TP: {position.get("takeProfit")} <br>
            SL: {position.get("stopLoss")}
        </p>
        <p class="small-text">
            Leverage: {position.get("leverage")}x
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.progress((roi + 100) / 200)


def render_order_card(order):
    side = order.get("side")
    side_color = "#00ff99" if str(side).lower() == "buy" else "#ff4b4b"

    st.markdown(f"""
    <div class="metric-card">
        <h3>{order.get("symbol")}</h3>
        <p>
            Side:
            <span style="color:{side_color}; font-weight:bold;">{side}</span>
        </p>
        <p>Type: {order.get("orderType")}</p>
        <p>Qty: {order.get("qty")}</p>
        <p>Price: {order.get("price")}</p>
        <p>Trigger: {order.get("triggerPrice")}</p>
        <p>Status: {order.get("orderStatus")}</p>
    </div>
    """, unsafe_allow_html=True)


def render_history_card(trade):
    pnl = trade.get("pnl", 0)
    pnl_class = "green" if pnl >= 0 else "red"
    emoji = "🟢" if pnl >= 0 else "🔴"

    st.markdown(f"""
    <div class="metric-card">
        <h3>{emoji} {trade.get("symbol")}</h3>
        <p>Result: {trade.get("result")}</p>
        <p>Entry: {trade.get("entry")}</p>
        <p>Exit: {trade.get("exit_price")}</p>
        <p class="{pnl_class}">PnL: {round(pnl, 4)}</p>
    </div>
    """, unsafe_allow_html=True)


def render_feed_card(trade):
    pnl = trade.get("pnl", 0)
    emoji = "🟢" if pnl >= 0 else "🔴"
    pnl_class = "green" if pnl >= 0 else "red"

    st.markdown(f"""
    <div class="feed-card">
        <strong>{emoji} {trade.get("symbol")}</strong><br>
        Result: {trade.get("result")}<br>
        <span class="{pnl_class}">PnL: {round(pnl, 4)}</span>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# AUTO REFRESH
# =========================================================

st_autorefresh(interval=2000, key="refresh")

# =========================================================
# SESSION EXECUTOR
# =========================================================

if "executor" not in st.session_state:
    st.session_state.executor = executor

# =========================================================
# CACHED API CALLS
# =========================================================

@st.cache_data(ttl=5)
def get_balance_cached():
    try:
        return st.session_state.executor.get_balance()
    except Exception as e:
        print(f"[BALANCE ERROR] {e}")
        return 0

# =========================================================
# LOAD DATA
# =========================================================

active_trades_json = load_active_trades()
closed_trades = load_closed_trades()

live_positions = executor.get_all_positions()
open_orders = executor.get_open_orders()

current_balance = get_balance_cached() or 0.0

# =========================================================
# CALCULATIONS
# =========================================================

floating_pnl = round(
    sum(float(p.get("unrealisedPnl", 0)) for p in live_positions),
    4
)

closed_pnl = round(
    sum(t.get("pnl", 0) for t in closed_trades),
    4
)

equity_live = round(
    current_balance + floating_pnl,
    4
)

total_exposure = round(
    sum(abs(float(p.get("positionValue", 0))) for p in live_positions),
    2
)

margin_ratio = 0
if equity_live > 0:
    margin_ratio = total_exposure / equity_live

real_open_positions = len([
    p for p in live_positions
    if abs(float(p.get("size", 0))) > 0
])

json_open_positions = len([
    t for t in active_trades_json
    if t.get("status") == "OPEN"
    and t.get("is_active") is True
])

# =========================================================
# HEADER
# =========================================================

st.title("📊 TRADEBOT_PRO | LIVE CONSOLE")

# =========================================================
# WARNINGS
# =========================================================

if json_open_positions != real_open_positions:
    st.warning(
        f"⚠️ STATE DESYNC | JSON: {json_open_positions} | EXCHANGE: {real_open_positions}"
    )

if margin_ratio >= 4:
    st.error(f"🚨 HIGH RISK | Margin Ratio: {round(margin_ratio, 2)}x")
elif margin_ratio >= 2:
    st.warning(f"⚠️ Elevated Exposure | Margin Ratio: {round(margin_ratio, 2)}x")
else:
    st.success(f"✅ Exposure Healthy | Margin Ratio: {round(margin_ratio, 2)}x")

# =========================================================
# TOP METRICS
# =========================================================

m1, m2, m3, m4, m5, m6 = st.columns(6)

metrics = [
    ("Equity", equity_live),
    ("Floating PnL", floating_pnl),
    ("Closed PnL", closed_pnl),
    ("Balance", current_balance),
    ("Open Positions", real_open_positions),
    ("Exposure", total_exposure),
]

for col, (title, value) in zip(
    [m1, m2, m3, m4, m5, m6],
    metrics
):
    with col:
        render_metric_card(title, value)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ ENGINE STATUS")

st.sidebar.success("Execution Engine")
st.sidebar.success("Bybit API")
st.sidebar.success("Risk Engine")
st.sidebar.success("Trade Reconciliation")

if margin_ratio > 3:
    st.sidebar.error("High Exposure")
else:
    st.sidebar.success("Exposure Safe")

st.sidebar.info(
    f"Last Sync: {time.strftime('%H:%M:%S')}"
)

st.sidebar.divider()

if st.sidebar.button("🗑 RESET ALL TRADES"):
    for file in ["active_trades.json", "closed_trades.json", "trades.json"]:
        path = f"storage/{file}"
        if os.path.exists(path):
            with open(path, "w") as f:
                f.write("[]")
    st.sidebar.warning("Storage Cleared")
    time.sleep(1)
    st.rerun()

# =========================================================
# TABS
# =========================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 Active Exposure",
    "📋 Open Orders",
    "📜 History",
    "📈 Analytics",
    "⚡ Live Feed"
])

# =========================================================
# TAB 1 - ACTIVE POSITIONS
# =========================================================

with tab1:
    st.subheader("🎯 Live Market Exposure")
    if not live_positions:
        st.info("No active positions.")
    else:
        for p in live_positions:
            try:
                render_position_card(p)
            except Exception as e:
                st.error(f"Error rendering position: {e}")

# =========================================================
# TAB 2 - OPEN ORDERS
# =========================================================

with tab2:
    st.subheader("📋 Open Orders")
    if not open_orders:
        st.info("No open orders.")
    else:
        for o in open_orders:
            if not isinstance(o, dict):
                continue
            render_order_card(o)

# =========================================================
# TAB 3 - HISTORY
# =========================================================

with tab3:
    st.subheader(f"📜 Trade History ({len(closed_trades)})")
    if not closed_trades:
        st.info("No trade history.")
    else:
        recent = list(reversed(closed_trades[-30:]))
        for t in recent:
            render_history_card(t)

# =========================================================
# TAB 4 - ANALYTICS
# =========================================================

with tab4:
    st.subheader("📈 Performance Analytics")
    if closed_trades:
        curve = []
        bal = current_balance - closed_pnl
        for t in closed_trades:
            bal += t.get("pnl", 0)
            curve.append(bal)

        st.line_chart(pd.DataFrame({"Equity": curve}))

        pair_stats = compute_pair_stats(closed_trades)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Winrate by Pair")
            st.bar_chart({p: pair_stats[p]["winrate"] for p in pair_stats})
        with c2:
            st.markdown("### Avg PnL by Pair")
            st.bar_chart({p: pair_stats[p]["avg_pnl"] for p in pair_stats})
    else:
        st.info("No analytics available.")

# =========================================================
# TAB 5 - LIVE FEED
# =========================================================

with tab5:
    st.subheader("⚡ Live Signal Feed")
    if not closed_trades:
        st.info("No feed available.")
    else:
        recent = list(reversed(closed_trades[-20:]))
        for t in recent:
            render_feed_card(t)

# =========================================================
# DEBUG PANEL
# =========================================================

with st.expander("🛠 Developer System State"):
    st.json({
        "equity_live": equity_live,
        "api_balance": current_balance,
        "floating_pnl": floating_pnl,
        "closed_pnl": closed_pnl,
        "exchange_positions": real_open_positions,
        "json_positions": json_open_positions,
        "open_orders": len(open_orders),
        "margin_ratio": margin_ratio,
        "desync": json_open_positions != real_open_positions
    })