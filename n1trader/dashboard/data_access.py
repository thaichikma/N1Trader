"""Pure data-access layer for the Streamlit dashboard (testable without UI)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from n1trader.optimize.metrics import expectancy, max_drawdown, profit_factor


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_positions(path: str | Path) -> pd.DataFrame:
    """Load position records parquet file."""
    df = pd.read_parquet(path)
    for col in ("entry_time", "exit_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)
    return df


def load_walk_forward(path: str | Path) -> pd.DataFrame:
    """Load walk-forward IS/OOS summary parquet."""
    return pd.read_parquet(path)


# ── KPI computation ───────────────────────────────────────────────────────────

def compute_kpis(positions: pd.DataFrame) -> dict:
    """Compute summary KPIs from a positions DataFrame."""
    if positions.empty:
        return {
            "n_trades": 0, "winrate": float("nan"),
            "profit_factor": float("nan"), "expectancy": float("nan"),
            "max_drawdown": float("nan"), "total_fees": 0.0,
            "total_pnl_net": 0.0,
        }

    pnl = positions["pnl_net"].dropna()
    wins = (pnl > 0).sum()
    n = len(pnl)
    equity = pnl.cumsum()

    return {
        "n_trades": n,
        "winrate": wins / n if n > 0 else float("nan"),
        "profit_factor": profit_factor(pnl),
        "expectancy": expectancy(pnl),
        "max_drawdown": max_drawdown(equity),
        "total_fees": float(positions.get("fees", pd.Series(dtype=float)).sum()),
        "total_pnl_net": float(pnl.sum()),
    }


# ── Filtering ─────────────────────────────────────────────────────────────────

def filter_positions(
    positions: pd.DataFrame,
    filter_set: str | None = None,
    regime: str | None = None,
    outcome: str | None = None,
    session: str | None = None,
    weekday: int | None = None,
    near_news: bool | None = None,
) -> pd.DataFrame:
    """Filter positions by any combination of the 4-dimension labels."""
    df = positions.copy()
    if filter_set is not None and "filter_set" in df.columns:
        df = df[df["filter_set"] == filter_set]
    if regime is not None and "regime" in df.columns:
        df = df[df["regime"] == regime]
    if outcome is not None and "outcome" in df.columns:
        df = df[df["outcome"] == outcome]
    if session is not None and "session" in df.columns:
        df = df[df["session"] == session]
    if weekday is not None and "weekday" in df.columns:
        df = df[df["weekday"] == weekday]
    if near_news is not None and "near_news" in df.columns:
        df = df[df["near_news"] == near_news]
    return df.reset_index(drop=True)


# ── Breakdown ─────────────────────────────────────────────────────────────────

def breakdown_by(positions: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Group positions by a label dimension and compute per-group KPIs."""
    if dimension not in positions.columns:
        return pd.DataFrame()
    groups = []
    for label, grp in positions.groupby(dimension):
        kpis = compute_kpis(grp)
        kpis[dimension] = label
        groups.append(kpis)
    return pd.DataFrame(groups).set_index(dimension) if groups else pd.DataFrame()


# ── IS / OOS table ────────────────────────────────────────────────────────────

def is_oos_table(wf_df: pd.DataFrame) -> pd.DataFrame:
    """Return a display-ready IS vs OOS comparison DataFrame."""
    cols = ["window", "best_param", "is_score", "oos_score", "oos_trades",
            "train_start", "test_start"]
    available = [c for c in cols if c in wf_df.columns]
    return wf_df[available].copy()
