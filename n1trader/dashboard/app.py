"""Streamlit entry point. Run with: streamlit run n1trader/dashboard/app.py"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from n1trader.dashboard.classification import render_classification
from n1trader.dashboard.compare import render_compare
from n1trader.dashboard.data_access import load_positions, load_walk_forward
from n1trader.dashboard.overview import render_overview
from n1trader.dashboard.trades import render_trades

st.set_page_config(page_title="N1Trader Dashboard", layout="wide")

DATA_DIR = Path("data/results")
POSITIONS_PATH = DATA_DIR / "positions.parquet"
WF_PATH = DATA_DIR / "walk_forward.parquet"


@st.cache_data
def _load_positions(path: Path) -> pd.DataFrame:
    if path.exists():
        return load_positions(path)
    return pd.DataFrame()


@st.cache_data
def _load_wf(path: Path) -> pd.DataFrame:
    if path.exists():
        return load_walk_forward(path)
    return pd.DataFrame()


def main() -> None:
    st.sidebar.title("N1Trader")
    page = st.sidebar.radio(
        "Page",
        ["Overview", "Trades", "Classification", "Compare IS/OOS"],
    )

    positions = _load_positions(POSITIONS_PATH)
    wf_df = _load_wf(WF_PATH)

    if page == "Overview":
        render_overview(positions)
    elif page == "Trades":
        render_trades(positions)
    elif page == "Classification":
        render_classification(positions)
    elif page == "Compare IS/OOS":
        render_compare(wf_df)


if __name__ == "__main__":
    main()
