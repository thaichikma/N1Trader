"""Tests for n1trader.optimize.windows."""
from __future__ import annotations

import pandas as pd
import pytest

from n1trader.optimize.windows import WFWindow, make_windows, slice_bars


def _make_bars(n: int = 1000) -> pd.DataFrame:
    t0 = pd.Timestamp("2025-01-06", tz="UTC")
    times = pd.date_range(t0, periods=n, freq="60s")
    return pd.DataFrame({
        "open_time": times,
        "close": [3000.0 + i for i in range(n)],
    })


def test_make_windows_returns_list():
    bars = _make_bars(500)
    windows = make_windows(bars["open_time"].iloc[0], bars["open_time"].iloc[-1],
                           train_bars=200, test_bars=100)
    assert isinstance(windows, list)
    assert len(windows) > 0


def test_windows_are_wfwindow_instances():
    bars = _make_bars(500)
    windows = make_windows(bars["open_time"].iloc[0], bars["open_time"].iloc[-1],
                           train_bars=200, test_bars=100)
    for w in windows:
        assert isinstance(w, WFWindow)


def test_oos_windows_non_overlapping():
    bars = _make_bars(1000)
    windows = make_windows(bars["open_time"].iloc[0], bars["open_time"].iloc[-1],
                           train_bars=300, test_bars=100)
    for i in range(len(windows) - 1):
        assert windows[i].oos_end <= windows[i + 1].oos_start, (
            f"Window {i} OOS end {windows[i].oos_end} overlaps window {i+1} OOS start {windows[i+1].oos_start}"
        )


def test_train_end_before_oos_start():
    bars = _make_bars(1000)
    windows = make_windows(bars["open_time"].iloc[0], bars["open_time"].iloc[-1],
                           train_bars=300, test_bars=100)
    for w in windows:
        assert w.train_end < w.oos_start


def test_slice_bars_returns_correct_subset():
    bars = _make_bars(500)
    windows = make_windows(bars["open_time"].iloc[0], bars["open_time"].iloc[-1],
                           train_bars=200, test_bars=100)
    w = windows[0]
    train_bars, oos_bars = slice_bars(bars, w)
    assert len(train_bars) > 0
    assert len(oos_bars) > 0


def test_no_leakage_train_oos():
    bars = _make_bars(1000)
    windows = make_windows(bars["open_time"].iloc[0], bars["open_time"].iloc[-1],
                           train_bars=300, test_bars=100)
    for w in windows:
        train_bars, oos_bars = slice_bars(bars, w)
        if len(train_bars) > 0 and len(oos_bars) > 0:
            assert train_bars["open_time"].max() < oos_bars["open_time"].min(), (
                "Train set bleeds into OOS — leakage detected"
            )


def test_anchored_mode_train_grows():
    bars = _make_bars(1000)
    windows_anchored = make_windows(
        bars["open_time"].iloc[0], bars["open_time"].iloc[-1],
        train_bars=300, test_bars=100, anchored=True,
    )
    if len(windows_anchored) > 1:
        _, oos0 = slice_bars(bars, windows_anchored[0])
        _, oos1 = slice_bars(bars, windows_anchored[1])
        train0, _ = slice_bars(bars, windows_anchored[0])
        train1, _ = slice_bars(bars, windows_anchored[1])
        assert len(train1) >= len(train0)
