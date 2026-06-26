"""Dashboard page 2: Trade table with 4-dimension filters."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from n1trader.dashboard.data_access import filter_positions


def render_trades(positions: pd.DataFrame) -> None:
    st.header("Trades")

    with st.sidebar:
        st.subheader("Filters")

        def _unique_opts(col: str) -> list[str]:
            if col not in positions.columns:
                return []
            return ["(all)"] + sorted(positions[col].dropna().unique().tolist())

        fs_opts = _unique_opts("filter_set")
        regime_opts = _unique_opts("regime")
        outcome_opts = _unique_opts("outcome")
        session_opts = _unique_opts("session")

        sel_fs = st.selectbox("Filter Set", fs_opts)
        sel_regime = st.selectbox("Regime", regime_opts)
        sel_outcome = st.selectbox("Outcome", outcome_opts)
        sel_session = st.selectbox("Session", session_opts)
        sel_near_news = st.selectbox("Near News", ["(all)", "Yes", "No"])

    filtered = filter_positions(
        positions,
        filter_set=None if sel_fs == "(all)" else sel_fs,
        regime=None if sel_regime == "(all)" else sel_regime,
        outcome=None if sel_outcome == "(all)" else sel_outcome,
        session=None if sel_session == "(all)" else sel_session,
        near_news=(None if sel_near_news == "(all)"
                   else (True if sel_near_news == "Yes" else False)),
    )

    st.write(f"Showing {len(filtered)} of {len(positions)} trades")

    display_cols = [c for c in [
        "entry_time", "exit_time", "side", "entry_price", "exit_price",
        "size", "pnl_net", "fees", "R", "mae", "mfe", "bars_held",
        "regime", "session", "outcome", "r_bucket",
    ] if c in filtered.columns]

    st.dataframe(filtered[display_cols], use_container_width=True)

    if not filtered.empty:
        st.subheader("Selected Trade Detail")
        idx = st.number_input("Trade index", min_value=0, max_value=len(filtered) - 1, value=0, step=1)
        st.json(filtered.iloc[int(idx)].to_dict())
