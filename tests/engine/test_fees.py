"""Tests for n1trader.engine.fees."""
from __future__ import annotations

import pytest

from n1trader.engine.fees import compute_commission


def test_taker_fee_long():
    notional = 10_000.0
    commission = compute_commission(notional, liquidity_side="TAKER", maker_fee=0.0002, taker_fee=0.0004)
    assert commission == pytest.approx(4.0)


def test_maker_fee_long():
    notional = 10_000.0
    commission = compute_commission(notional, liquidity_side="MAKER", maker_fee=0.0002, taker_fee=0.0004)
    assert commission == pytest.approx(2.0)


def test_zero_notional():
    commission = compute_commission(0.0, liquidity_side="TAKER", maker_fee=0.0002, taker_fee=0.0004)
    assert commission == pytest.approx(0.0)


def test_commission_proportional_to_notional():
    c1 = compute_commission(5_000.0, liquidity_side="TAKER", maker_fee=0.0002, taker_fee=0.0004)
    c2 = compute_commission(10_000.0, liquidity_side="TAKER", maker_fee=0.0002, taker_fee=0.0004)
    assert c2 == pytest.approx(c1 * 2)


def test_maker_less_than_taker():
    notional = 10_000.0
    maker = compute_commission(notional, liquidity_side="MAKER", maker_fee=0.0002, taker_fee=0.0004)
    taker = compute_commission(notional, liquidity_side="TAKER", maker_fee=0.0002, taker_fee=0.0004)
    assert maker < taker


def test_custom_fees():
    notional = 1000.0
    commission = compute_commission(notional, liquidity_side="TAKER", maker_fee=0.001, taker_fee=0.002)
    assert commission == pytest.approx(2.0)
