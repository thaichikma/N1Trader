"""Blackout rules: weekend UTC, news window ±30 min, cancel-limit mark."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from n1trader.data.news_windows import BlackoutWindow


def is_weekend_utc(ts: datetime) -> bool:
    """Return True when ts falls on Saturday (5) or Sunday (6) in UTC."""
    return ts.astimezone(timezone.utc).weekday() >= 5


def in_news_window(ts: datetime, windows: list[BlackoutWindow]) -> bool:
    """Return True when ts is inside any blackout window (inclusive bounds)."""
    for w in windows:
        if w.start_utc <= ts <= w.end_utc:
            return True
    return False


def cancel_due(ts: datetime, cancel_marks: list[datetime]) -> bool:
    """Return True when ts is within 60 s of any cancel mark (news_time − 30 min).

    Designed for live use: cancel pending limit orders when within 1 bar of
    the mark.  In backtest the function is unit-tested but never fires because
    the strategy uses market orders (no limits to cancel).
    """
    for mark in cancel_marks:
        if abs((ts - mark).total_seconds()) <= 60:
            return True
    return False
