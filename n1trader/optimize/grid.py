"""Walk-forward parameter grid generator."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterator


@dataclass(frozen=True)
class ParamSet:
    fast_period: int
    slow_period: int
    adx_threshold: float | None   # None = filter off
    use_atr_regime: bool
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.5

    def label(self) -> str:
        adx = f"adx{self.adx_threshold}" if self.adx_threshold else "noadx"
        atr = "atr" if self.use_atr_regime else "noatr"
        return f"ema{self.fast_period}_{self.slow_period}_{adx}_{atr}"


# Validated grid (Validation Session 1, plan §Open Questions)
_FAST_PERIODS = [9, 12, 21]
_SLOW_PERIODS = [26, 50, 100, 200]
_ADX_THRESHOLDS: list[float | None] = [None, 20.0, 25.0]
_ATR_REGIME = [False, True]


def generate_grid(
    fast_periods: list[int] = _FAST_PERIODS,
    slow_periods: list[int] = _SLOW_PERIODS,
    adx_thresholds: list[float | None] = _ADX_THRESHOLDS,
    use_atr_regime_opts: list[bool] = _ATR_REGIME,
    sl_atr_mult: float = 1.5,
    tp_atr_mult: float = 2.5,
) -> list[ParamSet]:
    """Return all valid EMA + filter combinations (fast < slow enforced)."""
    result: list[ParamSet] = []
    for fast, slow, adx, atr in product(
        fast_periods, slow_periods, adx_thresholds, use_atr_regime_opts
    ):
        if fast >= slow:
            continue
        result.append(ParamSet(
            fast_period=fast,
            slow_period=slow,
            adx_threshold=adx,
            use_atr_regime=atr,
            sl_atr_mult=sl_atr_mult,
            tp_atr_mult=tp_atr_mult,
        ))
    return result
