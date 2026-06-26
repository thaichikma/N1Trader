"""Walk-forward window cutter: rolling or anchored train/test splits."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class WFWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def make_windows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    train_bars: int,
    test_bars: int,
    bar_freq: str = "1min",
    anchored: bool = False,
) -> list[WFWindow]:
    """Generate non-overlapping train/test windows.

    anchored=False → rolling (train window slides forward).
    anchored=True  → expanding (train always starts at `start`).

    Train and test windows never overlap.
    OOS test windows cover the full period after the initial train window.
    """
    freq = pd.tseries.frequencies.to_offset(bar_freq)
    step = freq * test_bars  # roll forward by test_bars each iteration

    windows: list[WFWindow] = []
    train_start = start

    while True:
        train_end = train_start + freq * (train_bars - 1)
        test_start = train_end + freq
        test_end = test_start + freq * (test_bars - 1)

        if test_end > end:
            break

        windows.append(WFWindow(
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
        ))

        if anchored:
            # Expand train window: keep start fixed, move test forward
            train_start = start
        else:
            train_start = train_start + step

    return windows


def slice_bars(
    bars_df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    time_col: str = "open_time",
) -> pd.DataFrame:
    """Return rows of bars_df with time_col in [start, end]."""
    ts = pd.to_datetime(bars_df[time_col], utc=True)
    return bars_df.loc[(ts >= start) & (ts <= end)].reset_index(drop=True)
