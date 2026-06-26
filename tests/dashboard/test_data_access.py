"""Tests for n1trader.dashboard.data_access."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from n1trader.dashboard.data_access import (
    breakdown_by,
    compute_kpis,
    filter_positions,
    is_oos_table,
    load_positions,
)


def _make_positions_df(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame({
        "position_id": [f"P{i}" for i in range(n)],
        "side": (["LONG", "SHORT"] * (n // 2 + 1))[:n],
        "pnl_net": [20.0, -10.0, 15.0, -5.0, 25.0, -8.0, 30.0, -12.0, 18.0, -6.0][:n],
        "regime": (["trend", "sideways"] * (n // 2 + 1))[:n],
        "session": (["new_york", "london"] * (n // 2 + 1))[:n],
        "weekday": (["Monday", "Tuesday"] * (n // 2 + 1))[:n],
        "filter_set": (["filtered", "unfiltered"] * (n // 2 + 1))[:n],
        "outcome": (["win", "loss"] * (n // 2 + 1))[:n],
        "r_bucket": (["1R", "-0.5R"] * (n // 2 + 1))[:n],
        "near_news": ([False, True] * (n // 2 + 1))[:n],
        "is_oos": (["IS", "OOS"] * (n // 2 + 1))[:n],
        "entry_time": pd.date_range("2025-01-06", periods=n, freq="1h", tz="UTC"),
        "exit_time": pd.date_range("2025-01-06 00:30", periods=n, freq="1h", tz="UTC"),
    })


def test_load_positions_from_parquet(tmp_path):
    df = _make_positions_df(10)
    path = tmp_path / "positions.parquet"
    df.to_parquet(path)
    result = load_positions(path)
    assert len(result) == 10
    assert isinstance(result, pd.DataFrame)


def test_compute_kpis_returns_dict():
    df = _make_positions_df(10)
    kpis = compute_kpis(df)
    assert isinstance(kpis, dict)


def test_compute_kpis_has_n_trades():
    df = _make_positions_df(10)
    kpis = compute_kpis(df)
    assert "n_trades" in kpis
    assert kpis["n_trades"] == 10


def test_compute_kpis_has_winrate():
    df = _make_positions_df(10)
    kpis = compute_kpis(df)
    assert "winrate" in kpis
    assert 0.0 <= kpis["winrate"] <= 1.0


def test_filter_positions_by_regime():
    df = _make_positions_df(10)
    result = filter_positions(df, regime="trend")
    assert (result["regime"] == "trend").all()


def test_filter_positions_by_outcome():
    df = _make_positions_df(10)
    result = filter_positions(df, outcome="win")
    assert (result["outcome"] == "win").all()


def test_filter_positions_no_filter_returns_all():
    df = _make_positions_df(10)
    result = filter_positions(df)
    assert len(result) == 10


def test_breakdown_by_regime():
    df = _make_positions_df(10)
    bkd = breakdown_by(df, "regime")
    assert not bkd.empty
    assert "n_trades" in bkd.columns
    assert "total_pnl_net" in bkd.columns


def test_breakdown_by_session():
    df = _make_positions_df(10)
    bkd = breakdown_by(df, "session")
    assert "winrate" in bkd.columns


def test_is_oos_table_returns_dataframe():
    wf_df = pd.DataFrame({
        "window": [0, 1, 2],
        "is_score": [1.5, 1.2, 1.8],
        "oos_score": [1.1, 0.9, 1.3],
        "best_param": ["P1", "P2", "P1"],
    })
    result = is_oos_table(wf_df)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3


def test_is_oos_table_empty_input():
    result = is_oos_table(pd.DataFrame())
    assert isinstance(result, pd.DataFrame)
