"""Smoke tests for n1trader.engine.runner — backtest runs end-to-end."""
from __future__ import annotations

import tempfile

import pandas as pd
import pytest

from n1trader.data.catalog import load_to_catalog, query_bars
from n1trader.engine.runner import BacktestResult, run_backtest
from n1trader.strategy.ema_cross import EmaCrossConfig, EmaCrossStrategy


def _make_trending_bars(n: int = 300) -> list:
    t0 = pd.Timestamp("2025-01-06 00:00:00", tz="UTC")  # Monday
    times = pd.date_range(t0, periods=n, freq="60s")
    close = [3000.0 + i * 1.5 for i in range(n)]
    df = pd.DataFrame({
        "open_time": times,
        "open":  [c - 1 for c in close],
        "high":  [c + 8 for c in close],
        "low":   [c - 8 for c in close],
        "close": close,
        "volume": [500.0] * n,
    })
    with tempfile.TemporaryDirectory() as tmp:
        load_to_catalog(df, tmp)
        return query_bars(tmp)


@pytest.fixture(scope="function")
def backtest_result():
    bars = _make_trending_bars(300)
    config = EmaCrossConfig(
        instrument_id_str="ETH-PERP.BINANCE",
        bar_type_str="ETH-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        fast_period=5,
        slow_period=20,
    )
    strategy = EmaCrossStrategy(config)
    return run_backtest(bars, strategy, starting_balance=10_000)


@pytest.mark.slow
def test_runner_returns_backtest_result(backtest_result):
    assert isinstance(backtest_result, BacktestResult)


@pytest.mark.slow
def test_fills_dataframe_has_rows(backtest_result):
    assert len(backtest_result.fills) > 0


@pytest.mark.slow
def test_account_dataframe_not_empty(backtest_result):
    assert not backtest_result.account.empty


@pytest.mark.slow
def test_fees_are_positive(backtest_result):
    fills = backtest_result.fills
    if "commission" in fills.columns:
        assert (fills["commission"].abs() > 0).any()


@pytest.mark.slow
def test_positions_dataframe_exists(backtest_result):
    assert isinstance(backtest_result.positions, pd.DataFrame)
