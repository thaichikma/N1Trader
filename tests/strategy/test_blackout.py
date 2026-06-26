"""Tests for n1trader.strategy.blackout."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from n1trader.data.news_windows import BlackoutWindow
from n1trader.strategy.blackout import cancel_due, in_news_window, is_weekend_utc


def _utc(year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


# ── is_weekend_utc ────────────────────────────────────────────────────────────

def test_saturday_is_weekend():
    sat = _utc(2025, 1, 4)  # Saturday
    assert is_weekend_utc(sat) is True


def test_sunday_is_weekend():
    sun = _utc(2025, 1, 5)  # Sunday
    assert is_weekend_utc(sun) is True


def test_monday_is_not_weekend():
    mon = _utc(2025, 1, 6)  # Monday
    assert is_weekend_utc(mon) is False


def test_friday_is_not_weekend():
    fri = _utc(2025, 1, 3)  # Friday
    assert is_weekend_utc(fri) is False


# ── in_news_window ────────────────────────────────────────────────────────────

def _make_windows():
    news_time = _utc(2025, 1, 15, 14, 30)
    return [
        BlackoutWindow(
            start_utc=_utc(2025, 1, 15, 14, 0),
            end_utc=_utc(2025, 1, 15, 15, 0),
        )
    ]


def test_inside_news_window():
    windows = _make_windows()
    ts = _utc(2025, 1, 15, 14, 30)
    assert in_news_window(ts, windows) is True


def test_before_news_window():
    windows = _make_windows()
    ts = _utc(2025, 1, 15, 13, 59)
    assert in_news_window(ts, windows) is False


def test_after_news_window():
    windows = _make_windows()
    ts = _utc(2025, 1, 15, 15, 1)
    assert in_news_window(ts, windows) is False


def test_at_window_start_boundary():
    windows = _make_windows()
    ts = _utc(2025, 1, 15, 14, 0)
    assert in_news_window(ts, windows) is True


def test_empty_windows():
    assert in_news_window(_utc(2025, 1, 15, 14, 30), []) is False


# ── cancel_due ────────────────────────────────────────────────────────────────

def test_cancel_due_within_60s():
    mark = _utc(2025, 1, 15, 14, 0)
    ts = _utc(2025, 1, 15, 14, 0, 30)  # 30s after mark
    # cancel_due should return True within ±60s
    assert cancel_due(ts, [mark]) is True


def test_cancel_due_outside_60s():
    mark = _utc(2025, 1, 15, 14, 0)
    ts = _utc(2025, 1, 15, 14, 2)  # 2 min after mark
    assert cancel_due(ts, [mark]) is False


def test_cancel_due_before_mark_within_60s():
    mark = _utc(2025, 1, 15, 14, 0)
    # 30 seconds before mark
    from datetime import timedelta
    ts = mark - timedelta(seconds=30)
    assert cancel_due(ts, [mark]) is True


def test_cancel_due_empty_marks():
    assert cancel_due(_utc(2025, 1, 15, 14, 0), []) is False
