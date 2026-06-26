"""Dashboard page 1: Equity curve, drawdown, summary KPIs."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from n1trader.dashboard.data_access import compute_kpis


def render_overview(positions: pd.DataFrame) -> None:
    st.header("Overview")

    kpis = compute_kpis(positions)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trades", kpis["n_trades"])
    col2.metric("Win Rate", f"{kpis['winrate']:.1%}" if kpis["winrate"] == kpis["winrate"] else "n/a")
    col3.metric("Profit Factor", f"{kpis['profit_factor']:.2f}" if kpis["profit_factor"] == kpis["profit_factor"] else "n/a")
    col4.metric("Expectancy", f"{kpis['expectancy']:.2f}" if kpis["expectancy"] == kpis["expectancy"] else "n/a")

    col5, col6 = st.columns(2)
    col5.metric("Max Drawdown", f"{kpis['max_drawdown']:.2%}" if kpis["max_drawdown"] == kpis["max_drawdown"] else "n/a")
    col6.metric("Total Fees", f"{kpis['total_fees']:.2f} USDT")

    if positions.empty:
        st.info("No positions to display.")
        return

    pnl = positions["pnl_net"].fillna(0)
    equity = pnl.cumsum()

    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(y=equity.values, mode="lines", name="Equity"))
    fig_eq.update_layout(title="Equity Curve (cumulative PnL)", xaxis_title="Trade #", yaxis_title="USDT")
    st.plotly_chart(fig_eq, use_container_width=True)

    peak = equity.cummax()
    drawdown = (equity - peak) / peak.replace(0, float("nan"))
    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(y=drawdown.values, mode="lines", fill="tozeroy", name="Drawdown"))
    fig_dd.update_layout(title="Drawdown", xaxis_title="Trade #", yaxis_title="Fraction")
    st.plotly_chart(fig_dd, use_container_width=True)
