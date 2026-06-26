"""BacktestEngine runner: assembles venue + instrument + data + strategy and runs."""
from __future__ import annotations

import gc
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import MakerTakerFeeModel
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.trading.strategy import Strategy

from n1trader.engine.venue import BINANCE_VENUE, make_eth_perp_instrument


@dataclass
class BacktestResult:
    fills: pd.DataFrame
    positions: pd.DataFrame
    account: pd.DataFrame


def run_backtest(
    bars: list[Bar],
    strategy: Strategy,
    starting_balance: float = 10_000.0,
    maker_fee: Decimal = Decimal("0.0002"),
    taker_fee: Decimal = Decimal("0.0004"),
    trader_id: str = "BACKTEST-001",
) -> BacktestResult:
    """Run a single backtest and return fill/position/account reports."""
    engine = BacktestEngine(
        config=BacktestEngineConfig(trader_id=trader_id)
    )
    instrument = make_eth_perp_instrument(maker_fee=maker_fee, taker_fee=taker_fee)
    engine.add_venue(
        venue=BINANCE_VENUE,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=None,
        starting_balances=[Money(starting_balance, USDT)],
        fee_model=MakerTakerFeeModel(),
    )
    engine.add_instrument(instrument)
    engine.add_data(bars)
    engine.add_strategy(strategy)
    engine.run()

    fills = engine.trader.generate_order_fills_report()
    positions = engine.trader.generate_positions_report()
    account = engine.trader.generate_account_report(BINANCE_VENUE)

    engine.dispose()
    del engine
    gc.collect()

    return BacktestResult(fills=fills, positions=positions, account=account)
