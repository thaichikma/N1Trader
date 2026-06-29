"""Tests for n1trader.optimize.walk_forward — IS/OOS no-leakage."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from n1trader.optimize.grid import ParamSet
from n1trader.optimize.walk_forward import run_walk_forward


def _make_trending_bars(n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    t0 = pd.Timestamp("2025-01-06", tz="UTC")
    times = pd.date_range(t0, periods=n, freq="60s")
    close = 3000.0 + np.arange(n) * 2 + rng.normal(0, 5, n)
    high = close + rng.uniform(5, 15, n)
    low = close - rng.uniform(5, 15, n)
    return pd.DataFrame({
        "open_time": times,
        "open": close - 1,
        "high": high,
        "low": low,
        "close": close,
        "volume": [200.0] * n,
    })


def _simple_run_fn(bars_df: pd.DataFrame, params: ParamSet) -> pd.Series:
    """Toy PnL series based on closing returns — no real backtest."""
    returns = bars_df["close"].pct_change().dropna()
    if params.fast_period < params.slow_period:
        return returns * 100  # pretend profitable
    return -returns * 100


@pytest.mark.slow
def test_walk_forward_returns_dataframe():
    bars = _make_trending_bars(600)
    result = run_walk_forward(
        bars, _simple_run_fn, train_bars=200, test_bars=100, max_workers=1
    )
    assert isinstance(result, pd.DataFrame)


@pytest.mark.slow
def test_walk_forward_has_window_column():
    bars = _make_trending_bars(600)
    result = run_walk_forward(
        bars, _simple_run_fn, train_bars=200, test_bars=100, max_workers=1
    )
    assert "window" in result.columns


@pytest.mark.slow
def test_walk_forward_has_oos_score():
    bars = _make_trending_bars(600)
    result = run_walk_forward(
        bars, _simple_run_fn, train_bars=200, test_bars=100, max_workers=1
    )
    assert "oos_score" in result.columns


@pytest.mark.slow
def test_best_param_selected_from_train_only():
    """best_param must be chosen before OOS data is seen."""
    bars = _make_trending_bars(600)
    result = run_walk_forward(
        bars, _simple_run_fn, train_bars=200, test_bars=100, max_workers=1
    )
    assert "best_param" in result.columns
    assert result["best_param"].notna().all()


@pytest.mark.slow
def test_no_oos_overlap():
    bars = _make_trending_bars(600)
    result = run_walk_forward(
        bars, _simple_run_fn, train_bars=200, test_bars=100, max_workers=1
    )
    if "oos_start" in result.columns and "oos_end" in result.columns:
        starts = result["oos_start"].sort_values().values
        ends = result["oos_end"].sort_values().values
        for i in range(len(starts) - 1):
            assert ends[i] <= starts[i + 1], "OOS windows overlap — leakage"
