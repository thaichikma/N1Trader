"""Tests for n1trader.analysis.tagger — 6-label classification."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from n1trader.analysis.tagger import tag_positions
from n1trader.data.news_windows import BlackoutWindow


def _make_positions(n: int = 4) -> pd.DataFrame:
    t0 = pd.Timestamp("2025-01-06 14:00:00", tz="UTC")  # Monday afternoon
    entry_times = pd.date_range(t0, periods=n, freq="30min")
    exit_times = entry_times + pd.Timedelta(minutes=10)
    return pd.DataFrame({
        "position_id": [f"P{i}" for i in range(n)],
        "side": (["LONG", "SHORT"] * (n // 2 + 1))[:n],
        "entry_time": entry_times,
        "exit_time": exit_times,
        "pnl_net": [50.0, -20.0, 30.0, -10.0][:n],
        "entry_price": [3000.0] * n,
        "exit_price": [3050.0, 2980.0, 3030.0, 2990.0][:n],
    })


def _make_bars_df(n: int = 200) -> pd.DataFrame:
    t0 = pd.Timestamp("2025-01-06 00:00:00", tz="UTC")
    times = pd.date_range(t0, periods=n, freq="60s")
    import numpy as np
    rng = np.random.default_rng(7)
    close = 3000 + np.cumsum(rng.normal(0, 5, n))
    return pd.DataFrame({
        "open_time": times,
        "open": close - 1,
        "high": close + 10,
        "low": close - 10,
        "close": close,
        "volume": [100.0] * n,
    })


def _make_regime_df(bars_df: pd.DataFrame) -> pd.DataFrame:
    from n1trader.analysis.regime import classify_regime
    return classify_regime(bars_df)


def test_tag_positions_adds_six_labels():
    pos = _make_positions(4)
    bars = _make_bars_df(200)
    regime_df = _make_regime_df(bars)
    result = tag_positions(pos, bars, regime_df, blackout_windows=[], filter_set_map={})
    for col in ["filter_set", "regime", "outcome", "r_bucket", "session", "weekday"]:
        assert col in result.columns, f"Missing label column: {col}"


def test_near_news_column_present():
    pos = _make_positions(4)
    bars = _make_bars_df(200)
    regime_df = _make_regime_df(bars)
    result = tag_positions(pos, bars, regime_df, blackout_windows=[], filter_set_map={})
    assert "near_news" in result.columns


def test_weekday_is_correct():
    pos = _make_positions(1)
    bars = _make_bars_df(200)
    regime_df = _make_regime_df(bars)
    result = tag_positions(pos, bars, regime_df, blackout_windows=[], filter_set_map={})
    # entry_time is Monday 2025-01-06
    assert result["weekday"].iloc[0] in {"Monday", "Mon", 0, "0"}


def test_session_assigned():
    pos = _make_positions(4)
    bars = _make_bars_df(200)
    regime_df = _make_regime_df(bars)
    result = tag_positions(pos, bars, regime_df, blackout_windows=[], filter_set_map={})
    valid_sessions = {"asia", "europe", "us", "london", "new_york", "overlap", "unknown"}
    for s in result["session"].dropna():
        assert s.lower() in valid_sessions


def test_near_news_true_inside_window():
    pos = _make_positions(1)
    pos["entry_time"] = [pd.Timestamp("2025-01-06 14:20:00", tz="UTC")]
    windows = [BlackoutWindow(
        start_utc=datetime(2025, 1, 6, 14, 0, tzinfo=timezone.utc),
        end_utc=datetime(2025, 1, 6, 15, 0, tzinfo=timezone.utc),
    )]
    bars = _make_bars_df(200)
    regime_df = _make_regime_df(bars)
    result = tag_positions(pos, bars, regime_df, blackout_windows=windows, filter_set_map={})
    assert result["near_news"].iloc[0] is True or result["near_news"].iloc[0] == 1


def test_outcome_values_valid():
    pos = _make_positions(4)
    bars = _make_bars_df(200)
    regime_df = _make_regime_df(bars)
    result = tag_positions(pos, bars, regime_df, blackout_windows=[], filter_set_map={})
    valid = {"win", "loss", "breakeven"}
    for val in result["outcome"].dropna():
        assert val.lower() in valid
