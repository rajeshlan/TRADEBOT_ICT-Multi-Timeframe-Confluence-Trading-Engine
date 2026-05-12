import streamlit as st


def render_position_card(position):

    pnl = float(position.get("unrealisedPnl", 0))
    pos_val = abs(float(position.get("positionValue", 1)))

    roi = (pnl / pos_val) * 100 if pos_val > 0 else 0
    roi = max(min(roi, 100), -100)

    pnl_class = "green" if pnl >= 0 else "red"

    side = str(position.get("side", "")).upper()

    side_color = "#00ff99" if side == "BUY" else "#ff4b4b"

    symbol = position.get("symbol", "UNKNOWN")

    html = f"""<div class="metric-card glow">

<div style="
display:flex;
justify-content:space-between;
align-items:center;
margin-bottom:12px;
">

<div style="
font-size:24px;
font-weight:700;
">
{symbol}
</div>

<div style="
color:{side_color};
font-weight:700;
font-size:14px;
padding:4px 10px;
border-radius:999px;
background:rgba(255,255,255,0.06);
">
{side}
</div>

</div>

<div style="
display:grid;
grid-template-columns:1fr 1fr;
gap:10px;
margin-bottom:12px;
">

<div>
<div class="metric-title">PnL</div>
<div class="{pnl_class}" style="font-size:18px;">
{round(pnl, 4)}
</div>
</div>

<div>
<div class="metric-title">ROI</div>
<div class="{pnl_class}" style="font-size:18px;">
{round(roi, 2)}%
</div>
</div>

<div>
<div class="metric-title">Entry</div>
<div>{position.get("avgPrice")}</div>
</div>

<div>
<div class="metric-title">Mark</div>
<div>{position.get("markPrice")}</div>
</div>

<div>
<div class="metric-title">TP</div>
<div>{position.get("takeProfit")}</div>
</div>

<div>
<div class="metric-title">SL</div>
<div>{position.get("stopLoss")}</div>
</div>

</div>

<div style="
display:flex;
justify-content:space-between;
align-items:center;
margin-top:10px;
">

<div class="small-text">
Leverage: {position.get("leverage")}x
</div>

<div class="small-text">
Value: {round(pos_val, 2)}
</div>

</div>

</div>"""

    st.markdown(html, unsafe_allow_html=True)

    st.progress((roi + 100) / 200)