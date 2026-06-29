"""Download OHLCV bars from Binance USDⓈ-M Futures using python-binance."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pandas as pd
from binance.client import Client

_INTERVAL_MAP = {
    "1m": Client.KLINE_INTERVAL_1MINUTE,
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE,
    "1h": Client.KLINE_INTERVAL_1HOUR,
    "4h": Client.KLINE_INTERVAL_4HOUR,
    "1d": Client.KLINE_INTERVAL_1DAY,
}

_KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]


def _cache_path(cache_dir: str, symbol: str, interval: str, start: str, end: str | None) -> Path:
    key = hashlib.md5(f"{symbol}_{interval}_{start}_{end}".encode()).hexdigest()[:12]
    return Path(cache_dir) / f"{symbol}_{interval}_{key}.parquet"


def fetch_futures_ohlcv(
    symbol: str,
    interval: str = "1m",
    start: str = "1 Jan, 2025",
    end: str | None = None,
    api_key: str = "",
    api_secret: str = "",
    cache_dir: str | None = "data/cache",
) -> pd.DataFrame:
    """Fetch USDⓈ-M Futures OHLCV from Binance.

    Args:
        symbol:    e.g. "ETHUSDT"
        interval:  "1m" | "5m" | "15m" | "1h" | "4h" | "1d"
        start:     human-readable start e.g. "1 Jan, 2025"
        end:       human-readable end  e.g. "1 Jun, 2026" (None = now)
        cache_dir: directory for parquet cache; None to disable

    Returns:
        DataFrame with columns: open_time (UTC), open, high, low, close, volume
    """
    if cache_dir:
        cpath = _cache_path(cache_dir, symbol, interval, start, end)
        if cpath.exists():
            age_min = (time.time() - cpath.stat().st_mtime) / 60
            # Historical-only requests cached permanently; requests ending "now" refresh after 15min
            if end is not None or age_min < 15:
                return pd.read_parquet(cpath)

    client = Client(api_key, api_secret)
    interval_val = _INTERVAL_MAP.get(interval, Client.KLINE_INTERVAL_1MINUTE)

    klines = client.futures_historical_klines(
        symbol=symbol,
        interval=interval_val,
        start_str=start,
        end_str=end,
    )

    if not klines:
        return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(klines, columns=_KLINE_COLS)
    df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df = df[["open_time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)

    if cache_dir and not df.empty:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        df.to_parquet(cpath, index=False)

    return df
