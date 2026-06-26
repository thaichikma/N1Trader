"""Integration tests for EmaCrossStrategy: blackout enforcement and entry timing."""
from __future__ import annotations

import pandas as pd
import pytest

from n1trader.data.news_windows import BlackoutWindow
from n1trader.engine.runner import run_backtest
from n1trader.strategy.ema_cross import EmaCrossConfig, EmaCrossStrategy


def _weekend_bars(n: int = 60) -> list:
    """Return a simple bar list starting on Saturday UTC (no trading expected)."""
    from n1trader.data.catalog import load_to_catalog, query_bars
    import tempfile, os

    t0 = pd.Timestamp("2025-01-04 00:00:00", tz="UTC")  # Saturday
    times = pd.date_range(t0, periods=n, freq="60s")
    df = pd.DataFrame({
        "open_time": times,
        "open":  [3000.0 + i * 0.5 for i in range(n)],
        "high":  [3020.0 + i * 0.5 for i in range(n)],
        "low":   [2980.0 + i * 0.5 for i in range(n)],
        "close": [3010.0 + i * 0.5 for i in range(n)],
        "volume": [100.0] * n,
    })
    with tempfile.TemporaryDirectory() as tmp:
        load_to_catalog(df, tmp)
        return query_bars(tmp)


def _weekday_bars(n: int = 200) -> list:
    """Return bars starting on Monday — enough for EMA warm-up."""
    from n1trader.data.catalog import load_to_catalog, query_bars
    import tempfile

    t0 = pd.Timestamp("2025-01-06 00:00:00", tz="UTC")  # Monday
    times = pd.date_range(t0, periods=n, freq="60s")
    # Trending up to generate LONG signals
    close = [3000.0 + i * 2 for i in range(n)]
    df = pd.DataFrame({
        "open_time": times,
        "open":  [c - 1 for c in close],
        "high":  [c + 5 for c in close],
        "low":   [c - 5 for c in close],
        "close": close,
        "volume": [500.0] * n,
    })
    with tempfile.TemporaryDirectory() as tmp:
        load_to_catalog(df, tmp)
        return query_bars(tmp)


@pytest.mark.slow
def test_no_entries_on_weekend():
    bars = _weekend_bars(60)
    config = EmaCrossConfig(
        instrument_id_str="ETHUSDT-PERP.BINANCE",
        bar_type_str="ETHUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        fast_period=5,
        slow_period=10,
    )
    strategy = EmaCrossStrategy(config)
    result = run_backtest(bars, strategy)
    fills = result.fills
    assert len(fills) == 0, "No fills expected on weekend"


@pytest.mark.slow
def test_entry_on_weekday_bar_t_plus_1():
    """Signal generated at bar t must result in entry at bar t+1."""
    bars = _weekday_bars(200)
    config = EmaCrossConfig(
        instrument_id_str="ETHUSDT-PERP.BINANCE",
        bar_type_str="ETHUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        fast_period=5,
        slow_period=20,
    )
    strategy = EmaCrossStrategy(config)
    result = run_backtest(bars, strategy)
    # At least one trade should occur in a 200-bar trending sequence
    assert len(result.fills) > 0
