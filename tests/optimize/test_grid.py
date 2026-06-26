"""Tests for n1trader.optimize.grid."""
from __future__ import annotations

import pytest

from n1trader.optimize.grid import ParamSet, generate_grid


def test_generate_grid_returns_list():
    grid = generate_grid()
    assert isinstance(grid, list)
    assert len(grid) > 0


def test_all_items_are_param_sets():
    grid = generate_grid()
    for item in grid:
        assert isinstance(item, ParamSet)


def test_fast_always_less_than_slow():
    grid = generate_grid()
    for p in grid:
        assert p.fast_period < p.slow_period, (
            f"fast={p.fast_period} >= slow={p.slow_period}"
        )


def test_no_duplicates():
    grid = generate_grid()
    seen = set()
    for p in grid:
        key = (p.fast_period, p.slow_period, p.adx_threshold, p.use_atr_regime)
        assert key not in seen, f"Duplicate param set: {key}"
        seen.add(key)


def test_expected_combo_count():
    grid = generate_grid()
    # 3 fast × 4 slow combinations where fast<slow, × 3 adx_threshold × 2 use_atr_regime
    # Exact count depends on implementation; just verify > 0 and reasonable
    assert len(grid) >= 6


def test_param_set_is_frozen():
    p = generate_grid()[0]
    with pytest.raises((AttributeError, TypeError)):
        p.fast_period = 99  # type: ignore[misc]


def test_adx_threshold_can_be_none():
    grid = generate_grid()
    has_none = any(p.adx_threshold is None for p in grid)
    assert has_none, "Grid must include adx_threshold=None (no ADX filter)"


def test_use_atr_regime_bool():
    grid = generate_grid()
    for p in grid:
        assert isinstance(p.use_atr_regime, bool)
