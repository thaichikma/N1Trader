"""Attach 4-dimension classification labels to position records."""
from __future__ import annotations

import pandas as pd


# UTC hour ranges for trading sessions
_SESSION_RANGES = {
    "asia": (0, 8),
    "europe": (8, 16),
    "us": (16, 24),
}


def _session(hour_utc: int) -> str:
    for name, (start, end) in _SESSION_RANGES.items():
        if start <= hour_utc < end:
            return name
    return "asia"   # fallback for hour=23 wrap-around


def _r_bucket(r: float) -> str:
    if pd.isna(r):
        return "na"
    if r < -2:
        return "<-2R"
    if r < -1:
        return "-2R_-1R"
    if r < 0:
        return "-1R_0R"
    if r < 1:
        return "0R_1R"
    if r < 2:
        return "1R_2R"
    return ">2R"


def tag_positions(
    positions: pd.DataFrame,
    bars_df: pd.DataFrame,
    regime_df: pd.DataFrame | None = None,
    blackout_windows: list | None = None,
    filter_set_map: dict | None = None,
) -> pd.DataFrame:
    """Add 4-dimension label columns to a positions DataFrame.

    Dimensions added:
    - filter_set: string describing active filters at entry (from filter_set_map
      or 'default' if not provided)
    - regime: trend_dir + vol_regime at entry bar (from regime_df or 'unknown')
    - outcome: 'win' or 'loss'
    - r_bucket: R-multiple bucket string
    - session: 'asia' | 'europe' | 'us'
    - weekday: 0-4 (Mon-Fri)
    - near_news: True if entry_time is within 60 min of any blackout window boundary
    """
    out = positions.copy()
    out["entry_time"] = pd.to_datetime(out["entry_time"], utc=True)

    if regime_df is not None:
        regime_lookup = (
            regime_df.set_index(pd.to_datetime(regime_df["open_time"], utc=True))
            ["regime"]
            .to_dict()
        )
    else:
        regime_lookup = {}

    records = []
    for _, row in out.iterrows():
        entry_t = row["entry_time"]
        hour = entry_t.hour if pd.notna(entry_t) else 0
        wday = entry_t.weekday() if pd.notna(entry_t) else 0

        # Regime at entry bar
        regime = regime_lookup.get(entry_t, "unknown")

        # Filter set label
        fs = (filter_set_map or {}).get(str(entry_t), "default")

        # Outcome
        outcome = "win" if row.get("win", row.get("pnl_net", 0) > 0) else "loss"

        # near_news: entry within 60 min of any window boundary
        near = False
        if blackout_windows:
            from datetime import timedelta
            for w in blackout_windows:
                if (
                    abs((entry_t - w.start_utc).total_seconds()) <= 3600
                    or abs((entry_t - w.end_utc).total_seconds()) <= 3600
                ):
                    near = True
                    break

        records.append({
            "filter_set": fs,
            "regime": regime,
            "outcome": outcome,
            "r_bucket": _r_bucket(row.get("R", float("nan"))),
            "session": _session(hour),
            "weekday": wday,
            "near_news": near,
        })

    label_df = pd.DataFrame(records, index=out.index)
    return pd.concat([out, label_df], axis=1)
