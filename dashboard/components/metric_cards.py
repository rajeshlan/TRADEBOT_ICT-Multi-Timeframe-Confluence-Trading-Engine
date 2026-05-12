import streamlit as st


def render_metric_card(title, value):

    html = f"""<div class="metric-card glow">

<div class="metric-title">{title}</div>

<div class="metric-value">{value}</div>

</div>"""

    st.markdown(html, unsafe_allow_html=True)