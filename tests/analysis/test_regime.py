"""Tests for n1trader.analysis.regime."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from n1trader.analysis.regime import classify_regime


def _make_bars(n: int = 100, trend: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    t0 = pd.Timestamp("2025-01-06", tz="UTC")
    times = pd.date_range(t0, periods=n, freq="60s")
    if trend:
        close = 3000.0 + np.arange(n) * 5 + rng.normal(0, 1, n)
    else:
        close = 3000.0 + rng.normal(0, 1, n)  # random walk / sideways
    high = close + rng.uniform(5, 15, n)
    low = close - rng.uniform(5, 15, n)
    return pd.DataFrame({
        "open_time": times,
        "open": close - 1,
        "high": high,
        "low": low,
        "close": close,
        "volume": [100.0] * n,
    })


def test_classify_regime_returns_dataframe():
    bars = _make_bars(100)
    result = classify_regime(bars)
    assert isinstance(result, pd.DataFrame)


def test_regime_column_present():
    bars = _make_bars(100)
    result = classify_regime(bars)
    assert "regime" in result.columns


def test_adx_column_present():
    bars = _make_bars(100)
    result = classify_regime(bars)
    assert "adx" in result.columns


def test_atr_column_present():
    bars = _make_bars(100)
    result = classify_regime(bars)
    assert "atr" in result.columns


def test_vol_regime_column_present():
    bars = _make_bars(100)
    result = classify_regime(bars)
    assert "vol_regime" in result.columns


def test_trending_bars_produce_trend_regime():
    bars = _make_bars(200, trend=True)
    result = classify_regime(bars, adx_trend_threshold=20)
    late = result.iloc[50:]  # after warm-up
    assert late["regime"].str.startswith("trend_").any()


def test_regime_values_are_valid():
    bars = _make_bars(100)
    result = classify_regime(bars)
    # format is trend_{dir}_{vol}_vol, e.g. trend_up_high_vol
    unique = set(result["regime"].dropna().unique())
    for val in unique:
        assert val.startswith("trend_") or val == "sideways", f"Unexpected regime: {val}"


def test_output_length_matches_input():
    bars = _make_bars(80)
    result = classify_regime(bars)
    assert len(result) == len(bars)
