"""Tests for n1trader.analysis.positions."""
from __future__ import annotations

import pandas as pd
import pytest

from n1trader.analysis.positions import POSITION_COLS, positions_from_reports


def _make_fills(n: int = 4) -> pd.DataFrame:
    """Minimal fills DataFrame with required columns."""
    return pd.DataFrame({
        "trade_id": [f"T{i}" for i in range(n)],
        "instrument_id": ["ETH-PERP.BINANCE"] * n,
        "order_side": ["BUY", "SELL", "BUY", "SELL"][:n],
        "last_qty": [0.1] * n,
        "last_px": [3000.0, 3050.0, 2900.0, 2850.0][:n],
        "commission": [0.6, 0.61, 0.58, 0.57][:n],
        "ts_event": pd.date_range("2025-01-06", periods=n, freq="10min", tz="UTC"),
        "position_id": ["P1", "P1", "P2", "P2"][:n],
    })


def _make_positions_report(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame({
        "position_id": [f"P{i+1}" for i in range(n)],
        "instrument_id": ["ETH-PERP.BINANCE"] * n,
        "entry_price": [3000.0, 2900.0][:n],
        "avg_px_open": [3000.0, 2900.0][:n],
        "avg_px_close": [3050.0, 2850.0][:n],
        "realized_pnl": [5.0, -5.0][:n],
        "side": ["LONG", "SHORT"][:n],
        "ts_opened": pd.date_range("2025-01-06", periods=n, freq="20min", tz="UTC"),
        "ts_closed": pd.date_range("2025-01-06 00:10", periods=n, freq="20min", tz="UTC"),
    })


def test_positions_from_reports_returns_dataframe():
    fills = _make_fills(4)
    pos = _make_positions_report(2)
    result = positions_from_reports(fills, pos, initial_sl_map={})
    assert isinstance(result, pd.DataFrame)


def test_positions_columns_present():
    fills = _make_fills(4)
    pos = _make_positions_report(2)
    result = positions_from_reports(fills, pos, initial_sl_map={})
    for col in POSITION_COLS:
        assert col in result.columns, f"Missing column: {col}"


def test_pnl_net_equals_gross_minus_fees():
    fills = _make_fills(4)
    pos = _make_positions_report(2)
    result = positions_from_reports(fills, pos, initial_sl_map={})
    if "pnl_gross" in result.columns and "total_commission" in result.columns:
        expected_net = result["pnl_gross"] - result["total_commission"]
        pd.testing.assert_series_equal(
            result["pnl_net"].round(6),
            expected_net.round(6),
            check_names=False,
        )


def test_side_matches_fill_direction():
    fills = _make_fills(4)
    pos = _make_positions_report(2)
    result = positions_from_reports(fills, pos, initial_sl_map={})
    if "side" in result.columns:
        assert set(result["side"].unique()).issubset({"LONG", "SHORT"})
