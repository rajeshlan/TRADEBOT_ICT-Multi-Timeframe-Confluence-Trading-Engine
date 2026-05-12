import streamlit as st
import pandas as pd

def render_equity_chart(closed_trades):

    if not closed_trades:
        return

    pnl = [t.get("pnl", 0) for t in closed_trades]

    df = pd.DataFrame({
        "cumulative_pnl": pd.Series(pnl).cumsum()
    })

    st.line_chart(df["cumulative_pnl"], height=250)

def render_winrate_chart(stats):

    if not stats:
        return

    st.bar_chart({
        p: stats[p]["winrate"]
        for p in stats
    }, height=200)