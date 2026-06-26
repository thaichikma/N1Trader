"""Regime classifier: assigns trend direction and volatility label to each bar."""
from __future__ import annotations

import pandas as pd

from n1trader.strategy.filters import compute_adx, compute_atr


def classify_regime(
    bars_df: pd.DataFrame,
    adx_period: int = 14,
    adx_trend_threshold: float = 25.0,
    atr_period: int = 14,
    atr_vol_quantile: float = 0.6,
) -> pd.DataFrame:
    """Add regime columns to a bar DataFrame.

    Columns added:
    - adx: ADX value
    - atr: ATR value
    - trend_dir: 'up' | 'down' | 'sideways'
    - vol_regime: 'high' | 'low'
    - regime: combined label, e.g. 'trend_up_high_vol'

    Parameters
    ----------
    bars_df:
        OHLCV DataFrame with open_time, open, high, low, close.
    adx_trend_threshold:
        ADX > threshold → trending; else sideways.
    atr_vol_quantile:
        ATR > expanding quantile → high volatility.
    """
    df = bars_df.copy()
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    df["adx"] = compute_adx(high, low, close, adx_period)
    df["atr"] = compute_atr(high, low, close, atr_period)

    # Trend direction: use EMA slope proxy (close > close.shift(adx_period) → up)
    df["_ema"] = close.ewm(span=adx_period, adjust=False).mean()
    trend_up = df["adx"] >= adx_trend_threshold
    price_rising = df["_ema"] > df["_ema"].shift(1)

    df["trend_dir"] = "sideways"
    df.loc[trend_up & price_rising, "trend_dir"] = "up"
    df.loc[trend_up & ~price_rising, "trend_dir"] = "down"

    # Volatility regime
    atr_threshold = df["atr"].expanding(min_periods=adx_period).quantile(atr_vol_quantile)
    df["vol_regime"] = "low"
    df.loc[df["atr"] > atr_threshold, "vol_regime"] = "high"

    df["regime"] = "trend_" + df["trend_dir"] + "_" + df["vol_regime"] + "_vol"
    df.drop(columns=["_ema"], inplace=True)

    return df
