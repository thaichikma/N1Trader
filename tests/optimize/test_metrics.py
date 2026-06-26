"""Tests for n1trader.optimize.metrics — numerical correctness."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from n1trader.optimize.metrics import (
    expectancy,
    max_drawdown,
    profit_factor,
    score_params,
    sharpe_ratio,
)


def test_sharpe_ratio_positive_returns():
    pnl = pd.Series([10.0, 12.0, 8.0, 15.0, 11.0, 9.0, 13.0])
    sr = sharpe_ratio(pnl)
    assert sr > 0


def test_sharpe_ratio_negative_returns():
    pnl = pd.Series([-10.0, -5.0, -8.0, -12.0])
    sr = sharpe_ratio(pnl)
    assert sr < 0


def test_sharpe_ratio_zero_std():
    pnl = pd.Series([5.0, 5.0, 5.0, 5.0])
    sr = sharpe_ratio(pnl)
    assert sr == 0.0 or np.isnan(sr) or np.isinf(sr)


def test_profit_factor_basic():
    # 3 wins of 10, 2 losses of -5 → PF = 30/10 = 3.0
    pnl = pd.Series([10.0, 10.0, 10.0, -5.0, -5.0])
    pf = profit_factor(pnl)
    assert pf == pytest.approx(3.0)


def test_profit_factor_no_losses():
    pnl = pd.Series([10.0, 20.0, 5.0])
    pf = profit_factor(pnl)
    assert pf == float("inf") or pf > 100


def test_profit_factor_no_wins():
    pnl = pd.Series([-10.0, -5.0])
    pf = profit_factor(pnl)
    assert pf == 0.0 or pf < 0.01


def test_expectancy_positive():
    pnl = pd.Series([20.0, -5.0, 15.0, -5.0, 10.0])
    exp = expectancy(pnl)
    assert exp > 0


def test_expectancy_negative():
    pnl = pd.Series([-20.0, 5.0, -15.0, 3.0, -10.0])
    exp = expectancy(pnl)
    assert exp < 0


def test_max_drawdown_known_series():
    # Equity: 100, 90, 80, 95, 85 → max DD from 100 to 80 = 20%
    equity = pd.Series([100.0, 90.0, 80.0, 95.0, 85.0])
    dd = max_drawdown(equity)
    assert dd == pytest.approx(0.20, abs=0.01)


def test_max_drawdown_monotone_up():
    equity = pd.Series([100.0, 110.0, 120.0, 130.0])
    dd = max_drawdown(equity)
    assert dd == pytest.approx(0.0)


def test_score_params_sharpe():
    pnl = pd.Series([5.0, 10.0, 8.0, 12.0, 6.0])
    score = score_params(pnl, metric="sharpe")
    assert isinstance(score, float)


def test_score_params_profit_factor():
    pnl = pd.Series([10.0, -3.0, 8.0, -2.0])
    score = score_params(pnl, metric="profit_factor")
    assert score > 0
