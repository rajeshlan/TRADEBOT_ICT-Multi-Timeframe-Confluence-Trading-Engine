import streamlit as st

def render_risk_panel(margin_ratio):

    st.subheader("🛡 Risk & Orders")

    st.write(f"Margin Ratio: {round(margin_ratio, 2)}x")

    if margin_ratio >= 4:
        st.error("HIGH RISK")

    elif margin_ratio >= 2:
        st.warning("ELEVATED EXPOSURE")

    else:
        st.success("RISK HEALTHY")