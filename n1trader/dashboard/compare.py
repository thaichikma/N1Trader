"""Dashboard page 4: IS vs OOS comparison and parameter ranking."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from n1trader.dashboard.data_access import is_oos_table


def render_compare(wf_df: pd.DataFrame) -> None:
    st.header("Walk-Forward: IS vs OOS")

    if wf_df.empty:
        st.info("No walk-forward results found. Run Phase 5 first.")
        return

    table = is_oos_table(wf_df)
    st.subheader("IS vs OOS Score by Window")
    st.dataframe(table, use_container_width=True)

    if "is_score" in wf_df.columns and "oos_score" in wf_df.columns:
        fig = px.scatter(
            wf_df,
            x="is_score",
            y="oos_score",
            text="window" if "window" in wf_df.columns else None,
            title="IS Score vs OOS Score (overfit → top-left cluster)",
            labels={"is_score": "In-Sample Score", "oos_score": "Out-of-Sample Score"},
        )
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, xref="paper", yref="paper",
                      line=dict(dash="dash", color="gray"))
        st.plotly_chart(fig, use_container_width=True)

    if "best_param" in wf_df.columns and "oos_score" in wf_df.columns:
        st.subheader("Parameter Ranking (OOS score)")
        ranking = (
            wf_df.groupby("best_param")["oos_score"]
            .agg(["mean", "count"])
            .sort_values("mean", ascending=False)
            .rename(columns={"mean": "avg_oos_score", "count": "windows_selected"})
        )
        st.dataframe(ranking, use_container_width=True)
