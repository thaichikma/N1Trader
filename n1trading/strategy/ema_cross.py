"""EMA Cross strategy: signal generation on a DataFrame of OHLCV bars."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class EmaCrossConfig:
    fast_period: int = 12
    slow_period: int = 26
    atr_period: int = 14
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.5
    margin_pct: float = 0.05    # fraction of account used as margin
    leverage: int = 20
    size_precision: int = 3     # decimal places for qty (ETH: 0.001 min)
    # --- Filters ---
    adx_period: int = 14
    adx_threshold: float = 20.0  # only trade when ADX > threshold (market trending)
    atr_min_pct: float = 0.002   # only trade when ATR/close > 0.2% (enough volatility)


def _compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Average Directional Index using Wilder EWM (alpha = 1/period)."""
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    plus_dm_raw = high - prev_high
    minus_dm_raw = prev_low - low

    # +DM wins only when it's strictly larger than -DM and positive
    plus_dm = plus_dm_raw.where((plus_dm_raw > minus_dm_raw) & (plus_dm_raw > 0), 0.0)
    minus_dm = minus_dm_raw.where((minus_dm_raw > plus_dm_raw) & (minus_dm_raw > 0), 0.0)

    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)

    alpha = 1.0 / period
    tr_s = tr.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean() / tr_s)
    minus_di = 100 * (minus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean() / tr_s)

    di_sum = plus_di + minus_di
    dx = (100 * (plus_di - minus_di).abs() / di_sum).where(di_sum > 0, 0.0)
    return dx.ewm(alpha=alpha, min_periods=period, adjust=False).mean()


def generate_signals(df: pd.DataFrame, config: EmaCrossConfig) -> pd.DataFrame:
    """Compute EMA, ATR, ADX and cross signals on a DataFrame.

    Signal fires at bar t (causal); entry is at open of bar t+1.
    ATR filter  : signal blocked when ATR/close < atr_min_pct (low volatility)
    ADX filter  : signal blocked when ADX < adx_threshold (non-trending market)

    Returns a copy of df with added columns:
        ema_fast, ema_slow, atr, adx, signal (1=LONG, -1=SHORT, 0=NONE)
    """
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]

    df["ema_fast"] = close.ewm(span=config.fast_period, adjust=False, min_periods=config.fast_period).mean()
    df["ema_slow"] = close.ewm(span=config.slow_period, adjust=False, min_periods=config.slow_period).mean()

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    df["atr"] = tr.ewm(alpha=1.0 / config.atr_period, min_periods=config.atr_period, adjust=False).mean()
    df["adx"] = _compute_adx(high, low, close, config.adx_period)

    cross_long = (df["ema_fast"] > df["ema_slow"]) & (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1))
    cross_short = (df["ema_fast"] < df["ema_slow"]) & (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1))

    df["signal"] = 0
    df.loc[cross_long, "signal"] = 1
    df.loc[cross_short, "signal"] = -1

    # ATR filter: skip signal when market too quiet
    atr_pct = df["atr"] / df["close"]
    df.loc[atr_pct < config.atr_min_pct, "signal"] = 0

    # ADX filter: skip signal when market not trending
    df.loc[df["adx"] < config.adx_threshold, "signal"] = 0

    return df
