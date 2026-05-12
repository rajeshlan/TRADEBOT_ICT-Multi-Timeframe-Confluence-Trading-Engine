import streamlit as st


def render_history_card(trade):

    pnl = trade.get("pnl", 0)

    pnl_class = "green" if pnl >= 0 else "red"

    emoji = "🟢" if pnl >= 0 else "🔴"

    html = f"""<div class="metric-card">

<h3>{emoji} {trade.get("symbol")}</h3>

<p>
Result: {trade.get("result")}
</p>

<p>
Entry: {trade.get("entry")}
</p>

<p>
Exit: {trade.get("exit_price")}
</p>

<p class="{pnl_class}">
PnL: {round(pnl, 4)}
</p>

</div>"""

    st.markdown(html, unsafe_allow_html=True)