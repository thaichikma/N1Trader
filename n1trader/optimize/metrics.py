"""Performance metrics: Sharpe, Profit Factor, Expectancy, Max Drawdown."""
from __future__ import annotations

import math

import pandas as pd


def sharpe_ratio(pnl_series: pd.Series, periods_per_year: int = 252 * 390) -> float:
    """Annualised Sharpe ratio from a series of per-trade PnL values.

    Uses trade-level returns; periods_per_year scales annualisation.
    Returns NaN when std is zero or fewer than 2 samples.
    """
    s = pd.Series(pnl_series).dropna()
    if len(s) < 2 or s.std() == 0:
        return float("nan")
    return float(s.mean() / s.std() * math.sqrt(periods_per_year))


def profit_factor(pnl_series: pd.Series) -> float:
    """Gross profit / gross loss. Returns inf when no losses; 0 when no wins."""
    s = pd.Series(pnl_series).dropna()
    gross_profit = s[s > 0].sum()
    gross_loss = s[s < 0].abs().sum()
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else float("nan")
    return float(gross_profit / gross_loss)


def expectancy(pnl_series: pd.Series) -> float:
    """Average trade PnL (arithmetic expectancy)."""
    s = pd.Series(pnl_series).dropna()
    if s.empty:
        return float("nan")
    return float(s.mean())


def max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum drawdown from peak equity. Returns a positive number (magnitude)."""
    eq = pd.Series(equity_curve).dropna()
    if eq.empty:
        return float("nan")
    peak = eq.cummax()
    dd = (eq - peak) / peak.replace(0, float("nan"))
    return float(abs(dd.min()))


def score_params(pnl_series: pd.Series, metric: str = "expectancy") -> float:
    """Compute a single score for parameter selection during in-sample optimisation."""
    if metric == "sharpe":
        return sharpe_ratio(pnl_series)
    if metric == "profit_factor":
        return profit_factor(pnl_series)
    if metric == "expectancy":
        return expectancy(pnl_series)
    raise ValueError(f"Unknown metric: {metric!r}")
