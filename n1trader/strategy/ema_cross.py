"""Nautilus Strategy: EMA Cross with ATR-based SL/TP and blackout rules."""
from __future__ import annotations

import math
from collections import deque

import pandas as pd

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from n1trader.data.news_windows import BlackoutWindow
from n1trader.strategy.blackout import in_news_window, is_weekend_utc
from n1trader.strategy.signals import Signal, compute_ema


class EmaCrossConfig(StrategyConfig, frozen=True):
    instrument_id_str: str
    bar_type_str: str
    fast_period: int = 12
    slow_period: int = 26
    atr_period: int = 14
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.5
    # Position sizing: notional = account_balance * margin_pct * leverage
    margin_pct: float = 0.05   # 5% tài khoản làm margin
    leverage: int = 20         # đòn bảy x20
    size_precision: int = 3    # số thập phân ETH (Binance: 0.001 ETH min)


class EmaCrossStrategy(Strategy):
    """EMA cross strategy with ATR SL/TP and blackout guards.

    Signal fires at bar t (signal bar); entry happens at open of bar t+1.
    No look-ahead: EMAs are computed only on completed bars.
    """

    def __init__(self, config: EmaCrossConfig) -> None:
        super().__init__(config)
        buf = max(config.slow_period, config.atr_period) + 2
        self._closes: deque[float] = deque(maxlen=buf)
        self._highs: deque[float] = deque(maxlen=buf)
        self._lows: deque[float] = deque(maxlen=buf)
        self._blackout_windows: list[BlackoutWindow] = []
        self._cancel_marks: list = []
        self._pending_signal: int = 0
        self._sl_price: float | None = None
        self._tp_price: float | None = None
        self._initial_sl: float | None = None
        self._entry_side: int = 0
        self._last_atr: float = float("nan")
        self._instrument_id: InstrumentId = InstrumentId.from_str(
            config.instrument_id_str
        )

    def set_blackout_windows(
        self,
        windows: list[BlackoutWindow],
        cancel_marks: list,
    ) -> None:
        self._blackout_windows = windows
        self._cancel_marks = cancel_marks

    def on_start(self) -> None:
        self.subscribe_bars(BarType.from_str(self.config.bar_type_str))

    def on_bar(self, bar: Bar) -> None:
        self._closes.append(float(bar.close))
        self._highs.append(float(bar.high))
        self._lows.append(float(bar.low))

        bar_ts = pd.Timestamp(bar.ts_event, unit="ns", tz="UTC").to_pydatetime()

        if self._pending_signal != 0:
            blocked = is_weekend_utc(bar_ts) or in_news_window(
                bar_ts, self._blackout_windows
            )
            if not blocked and not self._has_open_position():
                self._open_position(self._pending_signal, bar)
        self._pending_signal = 0

        if self._has_open_position():
            self._check_exit(bar)
            return

        min_len = max(self.config.slow_period, self.config.atr_period) + 2
        if len(self._closes) < min_len:
            return

        close_ser = pd.Series(self._closes)
        high_ser = pd.Series(self._highs)
        low_ser = pd.Series(self._lows)

        self._last_atr = self._atr(high_ser, low_ser, close_ser, self.config.atr_period)

        ema_fast = compute_ema(close_ser, self.config.fast_period)
        ema_slow = compute_ema(close_ser, self.config.slow_period)

        last = len(close_ser) - 1
        cross_long = (
            ema_fast.iloc[last] > ema_slow.iloc[last]
            and ema_fast.iloc[last - 1] <= ema_slow.iloc[last - 1]
        )
        cross_short = (
            ema_fast.iloc[last] < ema_slow.iloc[last]
            and ema_fast.iloc[last - 1] >= ema_slow.iloc[last - 1]
        )

        if cross_long:
            self._pending_signal = Signal.LONG
        elif cross_short:
            self._pending_signal = Signal.SHORT

    def on_stop(self) -> None:
        instr_id = self._instrument_id
        self.cancel_all_orders(instr_id)
        self.close_all_positions(instr_id)

    def _has_open_position(self) -> bool:
        return self.portfolio.net_position(self._instrument_id) != 0

    def _atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int,
    ) -> float:
        prev_close = close.shift(1)
        tr = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1)
        val = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean().iloc[-1]
        return float(val)

    def _open_position(self, signal: int, bar: Bar) -> None:
        atr = self._last_atr
        if atr != atr or atr <= 0:
            return
        entry = float(bar.open)
        if entry <= 0:
            return

        qty = self._calc_qty(entry)
        if qty <= 0:
            return

        instr_id = self._instrument_id
        if signal == Signal.LONG:
            self._sl_price = entry - self.config.sl_atr_mult * atr
            self._tp_price = entry + self.config.tp_atr_mult * atr
            side = OrderSide.BUY
        else:
            self._sl_price = entry + self.config.sl_atr_mult * atr
            self._tp_price = entry - self.config.tp_atr_mult * atr
            side = OrderSide.SELL
        self._initial_sl = self._sl_price
        self._entry_side = signal
        order = self.order_factory.market(
            instrument_id=instr_id,
            order_side=side,
            quantity=Quantity(float(qty), self.config.size_precision),
        )
        self.submit_order(order)

    def _calc_qty(self, entry_price: float) -> float:
        """Return quantity in ETH (floored to size_precision).

        notional = balance * margin_pct * leverage
        qty      = floor(notional / entry_price, size_precision)
        """
        account = self.portfolio.account(self._instrument_id.venue)
        if account is None:
            return 0.0
        balance = account.balance_total(USDT)
        if balance is None:
            return 0.0
        notional = balance.as_double() * self.config.margin_pct * self.config.leverage
        scale = 10 ** self.config.size_precision
        # floor to avoid exceeding available margin
        return math.floor(notional / entry_price * scale) / scale

    def _check_exit(self, bar: Bar) -> None:
        if self._sl_price is None or self._tp_price is None:
            return
        instr_id = self._instrument_id
        lo = float(bar.low)
        hi = float(bar.high)

        hit_sl = (
            (self._entry_side == Signal.LONG and lo <= self._sl_price)
            or (self._entry_side == Signal.SHORT and hi >= self._sl_price)
        )
        hit_tp = (
            (self._entry_side == Signal.LONG and hi >= self._tp_price)
            or (self._entry_side == Signal.SHORT and lo <= self._tp_price)
        )

        if hit_sl or hit_tp:
            self.close_all_positions(instr_id)
            self._sl_price = None
            self._tp_price = None
            self._entry_side = 0
