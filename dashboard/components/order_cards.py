import streamlit as st


def render_order_card(order):

    if not isinstance(order, dict):
        return

    side = order.get("side")

    side_color = "#00ff99" if str(side).lower() == "buy" else "#ff4b4b"

    html = f"""<div class="metric-card">

<h3>{order.get("symbol")}</h3>

<p>
Side:
<span style="color:{side_color}; font-weight:bold;">
{side}
</span>
</p>

<p>
Type: {order.get("orderType")}
</p>

<p>
Qty: {order.get("qty")}
</p>

<p>
Price: {order.get("price")}
</p>

<p>
Status: {order.get("orderStatus")}
</p>

</div>"""

    st.markdown(html, unsafe_allow_html=True)