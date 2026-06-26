"""Regression: BacktestEngine must not crash when bar ts_event is valid."""

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import (
    AccountType,
    AggregationSource,
    BarAggregation,
    OmsType,
    PriceType,
)
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from n1trader.core.timestamp_utils import bar_timestamps_from_index


def test_backtest_engine_run_with_safe_bar_timestamps() -> None:
    engine = BacktestEngine(
        config=BacktestEngineConfig(
            trader_id="TESTER-001",
            logging=LoggingConfig(log_level="ERROR"),
        )
    )
    engine.add_venue(
        venue=Venue("BINANCE"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=None,
        starting_balances=[Money(10_000, USDT)],
    )
    instr = TestInstrumentProvider.ethusdt_perp_binance()
    engine.add_instrument(instr)
    bar_type = BarType(
        InstrumentId(Symbol("ETHUSDT-PERP"), Venue("BINANCE")),
        BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST),
        AggregationSource.EXTERNAL,
    )
    ts_event, ts_init = bar_timestamps_from_index(0)
    bars = [
        Bar(
            bar_type=bar_type,
            open=Price.from_str("3000.00"),
            high=Price.from_str("3010.00"),
            low=Price.from_str("2990.00"),
            close=Price.from_str("3005.00"),
            volume=Quantity.from_str("100.000"),
            ts_event=ts_event,
            ts_init=ts_init,
        )
    ]
    engine.add_data(bars)
    engine.run()
    engine.dispose()
