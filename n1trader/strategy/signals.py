"""Pure EMA-cross signal logic — no nautilus dependency, testable in isolation."""
from __future__ import annotations

from enum import IntEnum

import pandas as pd


class Signal(IntEnum):
    SHORT = -1
    NONE = 0
    LONG = 1


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average using EWM span (min_periods=period)."""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def generate_signals(
    close: pd.Series,
    fast_period: int,
    slow_period: int,
    filter_mask: pd.Series | None = None,
) -> pd.Series:
    """Generate EMA cross signals at bar t (signal bar).

    Signal is computed using only close[0..t] — causal, no look-ahead.
    Entry is intended at open of bar t+1; callers use get_entry_bar_index()
    to shift by one.

    Returns int Series: 1=LONG, -1=SHORT, 0=NONE, aligned with close.index.
    """
    ema_fast = compute_ema(close, fast_period)
    ema_slow = compute_ema(close, slow_period)

    # Crossover: fast crosses above slow → long
    cross_long = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
    cross_short = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

    signals = pd.Series(Signal.NONE, index=close.index, dtype=int)
    signals[cross_long] = int(Signal.LONG)
    signals[cross_short] = int(Signal.SHORT)

    if filter_mask is not None:
        signals[~filter_mask.fillna(False)] = int(Signal.NONE)

    return signals


def get_entry_bar_signals(signals: pd.Series) -> pd.Series:
    """Shift signals by one bar so entry happens at open of bar t+1 (no look-ahead)."""
    return signals.shift(1).fillna(0).astype(int)
