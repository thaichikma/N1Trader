"""Fee model config wrapper.

MakerTakerFeeModel (nautilus 1.221) reads maker_fee / taker_fee directly from
the instrument definition.  This module provides a thin helper to compute the
expected commission for a given fill so tests can validate correctness without
running a full engine.
"""
from __future__ import annotations

from decimal import Decimal


def compute_commission(
    notional_value: float,
    liquidity_side: str,  # "MAKER" or "TAKER"
    maker_fee: Decimal = Decimal("0.0002"),
    taker_fee: Decimal = Decimal("0.0004"),
) -> float:
    """Return commission in USDT for a fill with the given notional value.

    notional_value = fill_qty * fill_price  (for linear USDT-settled perp).
    """
    if liquidity_side == "MAKER":
        return float(notional_value * float(maker_fee))
    if liquidity_side == "TAKER":
        return float(notional_value * float(taker_fee))
    raise ValueError(f"Unknown liquidity_side: {liquidity_side!r}")
