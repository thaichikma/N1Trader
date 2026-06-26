#!/usr/bin/env python3
"""Smoke test for NautilusTrader BacktestEngine (ETHUSDT Perp + bars)."""

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import MakerTakerFeeModel
from nautilus_trader.config import LoggingConfig, StrategyConfig
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
from nautilus_trader.trading.strategy import Strategy

from n1trader.core.timestamp_utils import bar_timestamps_from_index


class SimpleCfg(StrategyConfig, frozen=True):
    bar_type: str


class SimpleStrat(Strategy):
    def __init__(self, config: SimpleCfg) -> None:
        super().__init__(config)
        self.bar_count = 0

    def on_start(self) -> None:
        self.subscribe_bars(BarType.from_str(self.config.bar_type))

    def on_bar(self, bar: Bar) -> None:
        self.bar_count += 1


def build_bars(bar_type: BarType, count: int = 50) -> list[Bar]:
    bars: list[Bar] = []
    for i in range(count):
        ts_event, ts_init = bar_timestamps_from_index(i)
        bars.append(
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
        )
    return bars


def main() -> None:
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
        fee_model=MakerTakerFeeModel(),
    )
    instr = TestInstrumentProvider.ethusdt_perp_binance()
    engine.add_instrument(instr)
    bar_type = BarType(
        InstrumentId(Symbol("ETHUSDT-PERP"), Venue("BINANCE")),
        BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST),
        AggregationSource.EXTERNAL,
    )
    engine.add_data(build_bars(bar_type))
    strat = SimpleStrat(
        config=SimpleCfg(strategy_id="EMA-001", bar_type=str(bar_type))
    )
    engine.add_strategy(strat)
    engine.run()
    print("bars_processed:", strat.bar_count)
    engine.dispose()


if __name__ == "__main__":
    main()
