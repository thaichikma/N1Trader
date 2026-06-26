"""Pure filter functions for ATR regime and ADX trend strength."""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average True Range via EWM smoothing (Wilder's method)."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average Directional Index (ADX) via Wilder's EWM smoothing."""
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(0.0, index=high.index, dtype=float)
    minus_dm = pd.Series(0.0, index=high.index, dtype=float)

    mask_up = (up_move > down_move) & (up_move > 0)
    mask_dn = (down_move > up_move) & (down_move > 0)
    plus_dm[mask_up] = up_move[mask_up]
    minus_dm[mask_dn] = down_move[mask_dn]

    atr = compute_atr(high, low, close, period)
    sm_plus = plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    sm_minus = minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    plus_di = 100.0 * sm_plus / atr.replace(0, np.nan)
    minus_di = 100.0 * sm_minus / atr.replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def filter_adx(adx: pd.Series, threshold: float) -> pd.Series:
    """Boolean mask: True where ADX > threshold."""
    return adx > threshold


def filter_atr_regime(
    atr: pd.Series,
    threshold: float | None = None,
    quantile: float = 0.5,
) -> pd.Series:
    """Boolean mask: True where ATR indicates trending (volatile) regime.

    If threshold is given, compares ATR > threshold directly.
    Otherwise uses a rolling expanding-window quantile as a dynamic threshold.
    """
    if threshold is not None:
        return atr > threshold
    dynamic = atr.expanding(min_periods=20).quantile(quantile)
    return atr > dynamic


def combine_filters(masks: list[pd.Series]) -> pd.Series:
    """AND-combine a list of boolean Series. Empty list returns all-True."""
    if not masks:
        raise ValueError("masks list must not be empty")
    result = masks[0].copy()
    for m in masks[1:]:
        result = result & m
    return result
