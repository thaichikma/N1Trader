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
    margin_pct: float = 0.05   # fraction of account used as margin
    leverage: int = 20
    size_precision: int = 3    # decimal places for qty (ETH: 0.001 min)


def generate_signals(df: pd.DataFrame, config: EmaCrossConfig) -> pd.DataFrame:
    """Compute EMA, ATR, and cross signals on a DataFrame.

    Signal fires at bar t (causal); entry is at open of bar t+1.

    Returns a copy of df with added columns:
        ema_fast, ema_slow, atr, signal (1=LONG, -1=SHORT, 0=NONE)
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

    cross_long = (df["ema_fast"] > df["ema_slow"]) & (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1))
    cross_short = (df["ema_fast"] < df["ema_slow"]) & (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1))

    df["signal"] = 0
    df.loc[cross_long, "signal"] = 1
    df.loc[cross_short, "signal"] = -1

    return df
