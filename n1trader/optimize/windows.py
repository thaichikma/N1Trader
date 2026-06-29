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

    @property
    def oos_start(self) -> pd.Timestamp:
        return self.test_start

    @property
    def oos_end(self) -> pd.Timestamp:
        return self.test_end


def make_windows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    train_bars: int,
    test_bars: int,
    bar_freq: str = "1min",
    anchored: bool = False,
) -> list[WFWindow]:
    """Generate non-overlapping train/test windows."""
    freq = pd.tseries.frequencies.to_offset(bar_freq)
    step = freq * test_bars

    windows: list[WFWindow] = []
    train_start = start
    anchored_extra = 0

    while True:
        if anchored:
            train_start = start
            train_end = start + freq * (train_bars - 1 + anchored_extra)
        else:
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
            anchored_extra += test_bars
        else:
            train_start = train_start + step

    return windows


def slice_bars(
    bars_df: pd.DataFrame,
    start: pd.Timestamp | WFWindow,
    end: pd.Timestamp | None = None,
    time_col: str = "open_time",
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    """Slice bars by [start, end] or by a WFWindow (train + test)."""
    if isinstance(start, WFWindow):
        window = start
        train = slice_bars(bars_df, window.train_start, window.train_end, time_col)
        test = slice_bars(bars_df, window.test_start, window.test_end, time_col)
        return train, test

    assert end is not None
    ts = pd.to_datetime(bars_df[time_col], utc=True)
    return bars_df.loc[(ts >= start) & (ts <= end)].reset_index(drop=True)
