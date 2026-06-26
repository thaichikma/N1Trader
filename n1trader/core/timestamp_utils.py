"""Safe Unix-nanosecond timestamps for NautilusTrader data objects."""

from __future__ import annotations

from datetime import datetime
from typing import Union

import pandas as pd
from nautilus_trader.core.datetime import dt_to_unix_nanos

DateLike = Union[datetime, pd.Timestamp, str]

# Nautilus BacktestEngine crashes (SIGABRT) when ts_event == 0.
_DEFAULT_EPOCH = pd.Timestamp("2025-01-01", tz="UTC")
DEFAULT_BAR_BASE_TS_NS = dt_to_unix_nanos(_DEFAULT_EPOCH)


def minute_bar_interval_nanos(minutes: int = 1) -> int:
    if minutes <= 0:
        raise ValueError(f"minutes must be positive, got {minutes}")
    return minutes * 60_000_000_000


def assert_positive_unix_nanos(ts: int, *, label: str = "ts_event") -> int:
    """Reject zero/negative timestamps before they reach the native engine."""
    if ts <= 0:
        raise ValueError(
            f"{label} must be a positive Unix nanosecond timestamp, got {ts}. "
            "NautilusTrader BacktestEngine aborts when ts_event is 0."
        )
    return ts


def to_unix_nanos(value: DateLike) -> int:
    """Convert a datetime-like value to validated Unix nanoseconds."""
    if isinstance(value, str):
        ts = pd.Timestamp(value, tz="UTC")
    elif isinstance(value, pd.Timestamp):
        ts = value.tz_convert("UTC") if value.tzinfo else value.tz_localize("UTC")
    else:
        ts = pd.Timestamp(value, tz="UTC")
    return assert_positive_unix_nanos(dt_to_unix_nanos(ts), label="timestamp")


def bar_timestamps_from_index(
    index: int,
    *,
    base_ts_ns: int | None = None,
    interval_ns: int | None = None,
) -> tuple[int, int]:
    """
    Build (ts_event, ts_init) for synthetic bar fixtures.

    Avoids ``index * interval`` alone, which yields ts_event=0 at index 0.
    """
    base = assert_positive_unix_nanos(
        base_ts_ns if base_ts_ns is not None else DEFAULT_BAR_BASE_TS_NS,
        label="base_ts_ns",
    )
    step = interval_ns if interval_ns is not None else minute_bar_interval_nanos()
    ts = assert_positive_unix_nanos(base + index * step, label="ts_event")
    return ts, ts
