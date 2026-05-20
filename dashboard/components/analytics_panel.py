import pandas as pd
import streamlit as st


def render_research_panel(summary_rows):
    st.subheader("Setup Research")

    if not summary_rows:
        st.caption("No classified setup outcomes yet.")
        return

    df = pd.DataFrame(summary_rows)
    visible = df[
        [
            "bias",
            "archetype",
            "market_regime",
            "session",
            "trades",
            "winrate",
            "net_pnl",
            "avg_pnl",
            "avg_mfe",
            "avg_mae",
        ]
    ]
    st.dataframe(
        visible.head(20),
        use_container_width=True,
        hide_index=True,
    )
