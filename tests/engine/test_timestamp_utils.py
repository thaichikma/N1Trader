import pytest

from n1trader.core.timestamp_utils import (
    DEFAULT_BAR_BASE_TS_NS,
    assert_positive_unix_nanos,
    bar_timestamps_from_index,
    to_unix_nanos,
)


def test_bar_timestamps_from_index_never_zero_at_index_zero() -> None:
    ts_event, ts_init = bar_timestamps_from_index(0)
    assert ts_event > 0
    assert ts_init == ts_event
    assert ts_event == DEFAULT_BAR_BASE_TS_NS


def test_bar_timestamps_from_index_increments_by_one_minute() -> None:
    ts0, _ = bar_timestamps_from_index(0)
    ts1, _ = bar_timestamps_from_index(1)
    assert ts1 - ts0 == 60_000_000_000


def test_assert_positive_unix_nanos_rejects_zero() -> None:
    with pytest.raises(ValueError, match="ts_event must be a positive"):
        assert_positive_unix_nanos(0)


def test_to_unix_nanos_from_utc_string() -> None:
    assert to_unix_nanos("2025-01-01T00:00:00Z") == DEFAULT_BAR_BASE_TS_NS
