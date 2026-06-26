"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def news_csv_path() -> Path:
    return FIXTURES_DIR / "news_sample.csv"


@pytest.fixture()
def sample_ohlcv_df() -> pd.DataFrame:
    """10 consecutive 1-minute bars starting at 2025-01-01 00:00 UTC."""
    t0 = pd.Timestamp("2025-01-01 00:00:00", tz="UTC")
    times = pd.date_range(t0, periods=10, freq="60s")
    return pd.DataFrame({
        "open_time": times,
        "open":  [3000.0 + i for i in range(10)],
        "high":  [3010.0 + i for i in range(10)],
        "low":   [2990.0 + i for i in range(10)],
        "close": [3005.0 + i for i in range(10)],
        "volume": [100.0 + i * 10 for i in range(10)],
    })
