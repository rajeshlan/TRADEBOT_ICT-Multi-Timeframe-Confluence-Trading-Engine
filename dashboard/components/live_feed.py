import streamlit as st


def render_live_feed(trade):

    pnl = trade.get("pnl", 0)

    emoji = "🟢" if pnl >= 0 else "🔴"

    pnl_class = "green" if pnl >= 0 else "red"

    html = f"""<div class="feed-card">

<strong>{emoji} {trade.get("symbol")}</strong>

<br><br>

Result: {trade.get("result")}

<br><br>

<span class="{pnl_class}">
PnL: {round(pnl, 4)}
</span>

</div>"""

    st.markdown(html, unsafe_allow_html=True)