"""Tests for n1trader.analysis.mae_mfe."""
from __future__ import annotations

import pandas as pd
import pytest

from n1trader.analysis.mae_mfe import compute_mae_mfe


def _make_bars_df(prices: list[tuple]) -> pd.DataFrame:
    """prices: list of (open, high, low, close) tuples."""
    n = len(prices)
    t0 = pd.Timestamp("2025-01-06 00:00:00", tz="UTC")
    times = pd.date_range(t0, periods=n, freq="60s")
    opens, highs, lows, closes = zip(*prices)
    return pd.DataFrame({
        "open_time": times,
        "open": list(opens),
        "high": list(highs),
        "low": list(lows),
        "close": list(closes),
        "volume": [100.0] * n,
    })


def _make_long_position(entry_time, exit_time, entry_price=3000.0, exit_price=3050.0, risk=50.0):
    return pd.DataFrame([{
        "position_id": "P1",
        "side": "LONG",
        "entry_time": entry_time,
        "exit_time": exit_time,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl_net": (exit_price - entry_price) * 0.1 - 1.0,
        "initial_sl": entry_price - risk,
    }])


def test_compute_mae_mfe_adds_columns():
    bars = _make_bars_df([(3000, 3100, 2950, 3050)] * 20)
    t0 = pd.Timestamp("2025-01-06 00:01:00", tz="UTC")
    t1 = pd.Timestamp("2025-01-06 00:10:00", tz="UTC")
    pos = _make_long_position(t0, t1)
    result = compute_mae_mfe(pos, bars)
    assert "mae" in result.columns
    assert "mfe" in result.columns


def test_long_mfe_positive_on_rising_market():
    # Price goes from 3000 up to 3100 during trade
    prices = [(3000 + i * 5, 3010 + i * 5, 2995 + i * 5, 3005 + i * 5) for i in range(20)]
    bars = _make_bars_df(prices)
    t0 = pd.Timestamp("2025-01-06 00:01:00", tz="UTC")
    t1 = pd.Timestamp("2025-01-06 00:15:00", tz="UTC")
    pos = _make_long_position(t0, t1, entry_price=3000.0, exit_price=3070.0)
    result = compute_mae_mfe(pos, bars)
    assert result["mfe"].iloc[0] > 0


def test_r_column_present():
    bars = _make_bars_df([(3000, 3100, 2950, 3050)] * 20)
    t0 = pd.Timestamp("2025-01-06 00:01:00", tz="UTC")
    t1 = pd.Timestamp("2025-01-06 00:10:00", tz="UTC")
    pos = _make_long_position(t0, t1)
    result = compute_mae_mfe(pos, bars)
    assert "R" in result.columns


def test_win_column_correct_for_positive_pnl():
    bars = _make_bars_df([(3000, 3100, 2950, 3050)] * 20)
    t0 = pd.Timestamp("2025-01-06 00:01:00", tz="UTC")
    t1 = pd.Timestamp("2025-01-06 00:10:00", tz="UTC")
    pos = _make_long_position(t0, t1, exit_price=3100.0)  # profitable
    result = compute_mae_mfe(pos, bars)
    assert "win" in result.columns
    assert result["win"].iloc[0] is True or result["win"].iloc[0] == 1
