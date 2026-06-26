"""Tests for n1trader.strategy.signals — including no-look-ahead proof."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from n1trader.strategy.signals import Signal, generate_signals, get_entry_bar_signals


def _rising_close(n: int = 50) -> pd.Series:
    """Flat then sharp rise — triggers a genuine fast/slow EMA crossover."""
    flat = [3000.0] * (n // 2)
    rising = [3000.0 + (i + 1) * 20 for i in range(n - n // 2)]
    return pd.Series(flat + rising)


def _falling_close(n: int = 50) -> pd.Series:
    """Flat then sharp fall — triggers a genuine fast/slow EMA crossover."""
    flat = [3000.0] * (n // 2)
    falling = [3000.0 - (i + 1) * 20 for i in range(n - n // 2)]
    return pd.Series(flat + falling)


def _flat_close(n: int = 50, value: float = 3000.0) -> pd.Series:
    return pd.Series([value] * n)


def test_generate_signals_returns_series():
    signals = generate_signals(_rising_close(), fast_period=5, slow_period=10)
    assert isinstance(signals, pd.Series)
    assert len(signals) == 50


def test_long_signal_on_rising_market():
    # Crossover fires once at the cross point — check the entire series
    close = _rising_close(100)
    signals = generate_signals(close, fast_period=5, slow_period=20)
    assert (signals == Signal.LONG).any()


def test_short_signal_on_falling_market():
    close = _falling_close(100)
    signals = generate_signals(close, fast_period=5, slow_period=20)
    assert (signals == Signal.SHORT).any()


def test_filter_mask_suppresses_signals():
    close = _rising_close(100)
    mask = pd.Series([False] * 100)  # suppress all
    signals = generate_signals(close, fast_period=5, slow_period=20, filter_mask=mask)
    assert (signals == Signal.NONE).all()


def test_filter_mask_none_passes_all():
    close = _rising_close(100)
    unfiltered = generate_signals(close, fast_period=5, slow_period=20)
    filtered = generate_signals(close, fast_period=5, slow_period=20, filter_mask=None)
    pd.testing.assert_series_equal(unfiltered, filtered)


# ── No-look-ahead proof ───────────────────────────────────────────────────────

def test_no_look_ahead_entry_shifted_by_one():
    """Entry signal at bar t must be based on signal at t-1, not t."""
    close = _rising_close(100)
    raw = generate_signals(close, fast_period=5, slow_period=20)
    entry = get_entry_bar_signals(raw)

    # Entry at index i == raw signal at index i-1
    for i in range(1, len(raw)):
        assert entry.iloc[i] == raw.iloc[i - 1], (
            f"Look-ahead at bar {i}: entry={entry.iloc[i]}, raw[i-1]={raw.iloc[i-1]}"
        )


def test_entry_bar_first_element_is_none():
    close = _rising_close(50)
    raw = generate_signals(close, fast_period=5, slow_period=10)
    entry = get_entry_bar_signals(raw)
    assert entry.iloc[0] == Signal.NONE


def test_signal_values_are_valid():
    close = _rising_close(50)
    signals = generate_signals(close, fast_period=5, slow_period=10)
    valid = {Signal.LONG, Signal.SHORT, Signal.NONE}
    assert set(signals.unique()).issubset(valid)
