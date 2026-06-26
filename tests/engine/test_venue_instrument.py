"""Tests for n1trader.engine.venue — instrument spec correctness."""
from __future__ import annotations

from decimal import Decimal

import pytest

from n1trader.engine.venue import make_eth_perp_instrument


def test_instrument_id_contains_eth():
    inst = make_eth_perp_instrument()
    assert "ETH" in str(inst.id).upper()


def test_price_precision_is_positive():
    inst = make_eth_perp_instrument()
    assert inst.price_precision >= 0


def test_size_precision_is_positive():
    inst = make_eth_perp_instrument()
    assert inst.size_precision >= 0


def test_maker_fee_stored_on_instrument():
    inst = make_eth_perp_instrument(maker_fee=Decimal("0.0002"), taker_fee=Decimal("0.0004"))
    assert inst.maker_fee == Decimal("0.0002")


def test_taker_fee_stored_on_instrument():
    inst = make_eth_perp_instrument(maker_fee=Decimal("0.0002"), taker_fee=Decimal("0.0004"))
    assert inst.taker_fee == Decimal("0.0004")


def test_custom_fees_accepted():
    inst = make_eth_perp_instrument(maker_fee=Decimal("0.001"), taker_fee=Decimal("0.002"))
    assert inst.maker_fee == Decimal("0.001")
    assert inst.taker_fee == Decimal("0.002")


def test_tick_size_positive():
    inst = make_eth_perp_instrument()
    assert inst.price_increment.as_decimal() > 0


def test_lot_size_positive():
    inst = make_eth_perp_instrument()
    assert inst.size_increment.as_decimal() > 0
