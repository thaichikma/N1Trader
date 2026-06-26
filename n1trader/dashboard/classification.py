"""Dashboard page 3: Performance breakdown by classification dimension."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from n1trader.dashboard.data_access import breakdown_by


_DIMENSIONS = ["regime", "session", "weekday", "filter_set", "outcome", "r_bucket"]


def render_classification(positions: pd.DataFrame) -> None:
    st.header("Classification Breakdown")

    available = [d for d in _DIMENSIONS if d in positions.columns]
    if not available:
        st.info("No label columns found — run tagger first.")
        return

    dim = st.selectbox("Breakdown dimension", available)
    bkd = breakdown_by(positions, dim)

    if bkd.empty:
        st.warning(f"No data for dimension '{dim}'.")
        return

    if "n_trades" in bkd.columns:
        fig_bar = px.bar(bkd.reset_index(), x=dim, y="n_trades", title="Trade Count per Group")
        st.plotly_chart(fig_bar, use_container_width=True)

    if "total_pnl_net" in bkd.columns:
        fig_pnl = px.bar(bkd.reset_index(), x=dim, y="total_pnl_net",
                         color="total_pnl_net", color_continuous_scale="RdYlGn",
                         title="Net PnL per Group")
        st.plotly_chart(fig_pnl, use_container_width=True)

    if "winrate" in bkd.columns:
        fig_wr = px.bar(bkd.reset_index(), x=dim, y="winrate",
                        title="Win Rate per Group", range_y=[0, 1])
        st.plotly_chart(fig_wr, use_container_width=True)

    st.subheader("Cross-dimension Heatmap")
    dim2_opts = [d for d in available if d != dim]
    if dim2_opts:
        dim2 = st.selectbox("Second dimension", dim2_opts)
        pivot = positions.groupby([dim, dim2])["pnl_net"].sum().unstack(fill_value=0)
        fig_heat = px.imshow(pivot, color_continuous_scale="RdYlGn",
                             title=f"Net PnL: {dim} × {dim2}")
        st.plotly_chart(fig_heat, use_container_width=True)

    st.subheader("Full Breakdown Table")
    st.dataframe(bkd, use_container_width=True)
