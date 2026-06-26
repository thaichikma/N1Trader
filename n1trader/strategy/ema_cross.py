"""Nautilus Strategy: EMA Cross with ATR-based SL/TP and blackout rules."""
from __future__ import annotations

import pandas as pd

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from n1trader.data.news_windows import BlackoutWindow
from n1trader.strategy.blackout import in_news_window, is_weekend_utc
from n1trader.strategy.signals import Signal


class EmaCrossConfig(StrategyConfig, frozen=True):
    instrument_id_str: str
    bar_type_str: str
    fast_period: int = 12
    slow_period: int = 26
    atr_period: int = 14
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.5
    trade_size_str: str = "0.100"


class EmaCrossStrategy(Strategy):
    """EMA cross strategy with ATR SL/TP and blackout guards.

    Signal fires at bar t (signal bar); entry happens at open of bar t+1.
    Indicators are updated incrementally — no per-bar pandas Series allocation.
    """

    def __init__(self, config: EmaCrossConfig) -> None:
        super().__init__(config)
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

        self._alpha_fast = 2.0 / (config.fast_period + 1)
        self._alpha_slow = 2.0 / (config.slow_period + 1)
        self._bar_count = 0
        self._prev_close: float | None = None
        self._ema_fast: float | None = None
        self._ema_slow: float | None = None
        self._ema_fast_prev: float | None = None
        self._ema_slow_prev: float | None = None
        self._atr: float | None = None
        self._tr_count = 0
        self._tr_sum = 0.0

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
            self._update_indicators(bar)
            return

        self._update_indicators(bar)

        min_len = max(self.config.slow_period, self.config.atr_period) + 2
        if self._bar_count < min_len:
            return
        if (
            self._ema_fast is None
            or self._ema_slow is None
            or self._ema_fast_prev is None
            or self._ema_slow_prev is None
        ):
            return

        cross_long = (
            self._ema_fast > self._ema_slow
            and self._ema_fast_prev <= self._ema_slow_prev
        )
        cross_short = (
            self._ema_fast < self._ema_slow
            and self._ema_fast_prev >= self._ema_slow_prev
        )

        if cross_long:
            self._pending_signal = Signal.LONG
        elif cross_short:
            self._pending_signal = Signal.SHORT

    def on_stop(self) -> None:
        instr_id = self._instrument_id
        self.cancel_all_orders(instr_id)
        self.close_all_positions(instr_id)

    def _update_indicators(self, bar: Bar) -> None:
        close = float(bar.close)
        high = float(bar.high)
        low = float(bar.low)

        self._bar_count += 1
        self._ema_fast_prev = self._ema_fast
        self._ema_slow_prev = self._ema_slow
        self._ema_fast = self._next_ema(close, self._ema_fast, self._alpha_fast)
        self._ema_slow = self._next_ema(close, self._ema_slow, self._alpha_slow)
        self._last_atr = self._next_atr(high, low, close)

    @staticmethod
    def _next_ema(value: float, prev: float | None, alpha: float) -> float:
        if prev is None:
            return value
        return alpha * value + (1.0 - alpha) * prev

    def _next_atr(self, high: float, low: float, close: float) -> float:
        if self._prev_close is None:
            self._prev_close = close
            return float("nan")

        tr = max(
            high - low,
            abs(high - self._prev_close),
            abs(low - self._prev_close),
        )
        self._prev_close = close
        period = self.config.atr_period

        if self._atr is None:
            self._tr_count += 1
            self._tr_sum += tr
            if self._tr_count < period:
                return float("nan")
            self._atr = self._tr_sum / period
            return self._atr

        self._atr = ((self._atr * (period - 1)) + tr) / period
        return self._atr

    def _has_open_position(self) -> bool:
        return self.portfolio.net_position(self._instrument_id) != 0

    def _open_position(self, signal: int, bar: Bar) -> None:
        atr = self._last_atr
        if atr != atr or atr <= 0:
            return
        entry = float(bar.open)
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
            quantity=Quantity.from_str(self.config.trade_size_str),
        )
        self.submit_order(order)

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
