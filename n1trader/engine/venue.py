"""BINANCE FUTURES venue and ETHUSDT-PERP instrument factory."""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model.currencies import ETH, USDT
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.test_kit.providers import TestInstrumentProvider

BINANCE_VENUE = Venue("BINANCE")
ETHUSDT_PERP_ID = InstrumentId(Symbol("ETHUSDT-PERP"), BINANCE_VENUE)


def make_eth_perp_instrument(
    maker_fee: Decimal = Decimal("0.0002"),
    taker_fee: Decimal = Decimal("0.0004"),
) -> CryptoPerpetual:
    """Return ETHUSDT-PERP instrument with configurable maker/taker fees.

    Defaults match Binance Futures standard tier: maker 0.02%, taker 0.04%.
    Precision and tick/step sizes match Binance ETHUSDT-PERP spec.
    """
    base = TestInstrumentProvider.ethusdt_perp_binance()
    # Re-create with overridable fees while keeping all other spec intact.
    return CryptoPerpetual(
        instrument_id=base.id,
        raw_symbol=base.raw_symbol,
        base_currency=ETH,
        quote_currency=USDT,
        settlement_currency=USDT,
        is_inverse=False,
        price_precision=base.price_precision,
        size_precision=base.size_precision,
        price_increment=base.price_increment,
        size_increment=base.size_increment,
        multiplier=base.multiplier,
        lot_size=base.lot_size,
        max_quantity=base.max_quantity,
        min_quantity=base.min_quantity,
        max_notional=base.max_notional,
        min_notional=base.min_notional,
        max_price=base.max_price,
        min_price=base.min_price,
        margin_init=base.margin_init,
        margin_maint=base.margin_maint,
        maker_fee=maker_fee,
        taker_fee=taker_fee,
        ts_event=0,
        ts_init=0,
    )
