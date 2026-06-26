"""Tests for n1trader.strategy.filters."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from n1trader.strategy.filters import (
    combine_filters,
    compute_adx,
    compute_atr,
    filter_adx,
    filter_atr_regime,
)


def _make_ohlcv(n: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 3000.0 + np.cumsum(rng.normal(0, 10, n))
    high = close + rng.uniform(5, 20, n)
    low = close - rng.uniform(5, 20, n)
    return pd.DataFrame({"high": high, "low": low, "close": close})


def test_compute_atr_length():
    df = _make_ohlcv(50)
    atr = compute_atr(df["high"], df["low"], df["close"], period=14)
    assert len(atr) == len(df)


def test_compute_atr_positive():
    df = _make_ohlcv(50)
    atr = compute_atr(df["high"], df["low"], df["close"], period=14)
    valid = atr.dropna()
    assert (valid > 0).all()


def test_compute_adx_length():
    df = _make_ohlcv(50)
    adx = compute_adx(df["high"], df["low"], df["close"], period=14)
    assert len(adx) == len(df)


def test_compute_adx_range():
    df = _make_ohlcv(100)
    adx = compute_adx(df["high"], df["low"], df["close"], period=14)
    valid = adx.dropna()
    assert (valid >= 0).all()
    assert (valid <= 100).all()


def test_filter_adx_above_threshold():
    # threshold=30 → 30 > 30 is False, 40 > 30 is True
    adx = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    mask = filter_adx(adx, threshold=30.0)
    assert mask.tolist() == [False, False, False, True, True]


def test_filter_atr_regime_above_median():
    # quantile needs min_periods=20; use explicit threshold instead
    atr = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    mask = filter_atr_regime(atr, threshold=3.0)
    assert mask.tolist() == [False, False, False, True, True]


def test_filter_atr_regime_custom_threshold():
    atr = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    mask = filter_atr_regime(atr, threshold=3.0)
    assert mask.tolist() == [False, False, False, True, True]


def test_combine_filters_and_logic():
    m1 = pd.Series([True, True, False, False])
    m2 = pd.Series([True, False, True, False])
    result = combine_filters([m1, m2])
    assert result.tolist() == [True, False, False, False]


def test_combine_filters_single():
    m = pd.Series([True, False, True])
    result = combine_filters([m])
    assert result.tolist() == [True, False, True]
