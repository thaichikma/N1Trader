"""Bar-by-bar backtester for EMA Cross strategy on OHLCV DataFrame."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from n1trading.strategy.ema_cross import EmaCrossConfig


@dataclass
class Trade:
    entry_bar: int
    entry_time: pd.Timestamp
    entry_price: float
    side: Literal["LONG", "SHORT"]
    qty: float
    sl_price: float
    tp_price: float
    exit_bar: int | None = None
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str | None = None  # "SL" | "TP" | "END"
    pnl: float | None = None


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: pd.Series
    starting_balance: float
    final_balance: float

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(1 for t in self.trades if (t.pnl or 0) > 0) / len(self.trades)

    @property
    def avg_win(self) -> float:
        wins = [t.pnl for t in self.trades if (t.pnl or 0) > 0]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t.pnl for t in self.trades if (t.pnl or 0) < 0]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl for t in self.trades if (t.pnl or 0) > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if (t.pnl or 0) < 0))
        return gross_profit / gross_loss if gross_loss else float("inf")

    @property
    def max_drawdown_pct(self) -> float:
        peak = self.equity_curve.cummax()
        dd = (self.equity_curve - peak) / peak
        return float(dd.min()) * 100

    @property
    def net_pnl(self) -> float:
        return self.final_balance - self.starting_balance

    @property
    def return_pct(self) -> float:
        return self.net_pnl / self.starting_balance * 100


def run_backtest(
    df: pd.DataFrame,
    config: EmaCrossConfig,
    starting_balance: float = 10_000.0,
    taker_fee: float = 0.0004,
) -> BacktestResult:
    """Simulate EMA Cross strategy bar by bar.

    Expects df to have columns: open_time, open, high, low, close, signal, atr.
    Signal at bar t → entry at open of bar t+1 (no look-ahead).
    """
    balance = starting_balance
    equity: list[float] = []
    trades: list[Trade] = []
    open_trade: Trade | None = None

    rows = df.reset_index(drop=True)

    for i in range(len(rows)):
        row = rows.iloc[i]
        bar_open = float(row["open"])
        bar_high = float(row["high"])
        bar_low = float(row["low"])
        bar_time = row["open_time"]

        # Check SL/TP for open trade
        if open_trade is not None:
            exit_price, exit_reason = _check_exit(open_trade, bar_high, bar_low)
            if exit_price is not None:
                pnl = _calc_pnl(open_trade, exit_price, taker_fee)
                balance += pnl
                open_trade.exit_bar = i
                open_trade.exit_time = bar_time
                open_trade.exit_price = exit_price
                open_trade.exit_reason = exit_reason
                open_trade.pnl = pnl
                trades.append(open_trade)
                open_trade = None

        equity.append(balance)

        # Entry: signal from previous bar fires at this bar's open
        if i == 0 or open_trade is not None:
            continue

        prev = rows.iloc[i - 1]
        signal = int(prev["signal"])
        atr = float(prev["atr"])

        if signal == 0 or math.isnan(atr) or atr <= 0:
            continue

        qty = _calc_qty(balance, config, bar_open)
        if qty <= 0:
            continue

        balance -= bar_open * qty * taker_fee  # entry fee

        if signal == 1:
            open_trade = Trade(
                entry_bar=i, entry_time=bar_time, entry_price=bar_open,
                side="LONG", qty=qty,
                sl_price=bar_open - config.sl_atr_mult * atr,
                tp_price=bar_open + config.tp_atr_mult * atr,
            )
        else:
            open_trade = Trade(
                entry_bar=i, entry_time=bar_time, entry_price=bar_open,
                side="SHORT", qty=qty,
                sl_price=bar_open + config.sl_atr_mult * atr,
                tp_price=bar_open - config.tp_atr_mult * atr,
            )

    # Force-close any open trade at last bar
    if open_trade is not None:
        last = rows.iloc[-1]
        exit_price = float(last["close"])
        pnl = _calc_pnl(open_trade, exit_price, taker_fee)
        balance += pnl
        open_trade.exit_bar = len(rows) - 1
        open_trade.exit_time = last["open_time"]
        open_trade.exit_price = exit_price
        open_trade.exit_reason = "END"
        open_trade.pnl = pnl
        trades.append(open_trade)

    equity_curve = pd.Series(equity, index=rows["open_time"], name="equity")
    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        starting_balance=starting_balance,
        final_balance=balance,
    )


def run_backtest_mtf(
    df_15m: pd.DataFrame,
    df_1m: pd.DataFrame,
    config: EmaCrossConfig,
    starting_balance: float = 10_000.0,
    taker_fee: float = 0.0004,
) -> BacktestResult:
    """Multi-timeframe backtest: signal on 15m, execution + SL/TP on 1m.

    Signal fires when 15m bar closes; entry at open of the corresponding 1m bar
    that starts at next 15m bar's open_time. SL/TP monitored bar-by-bar on 1m.
    """
    # Build a lookup: 1m open_time → row index for fast alignment
    df_1m = df_1m.reset_index(drop=True)
    time_to_1m = {t: i for i, t in enumerate(df_1m["open_time"])}

    balance = starting_balance
    equity: list[float] = []
    trades: list[Trade] = []
    open_trade: Trade | None = None

    # Track which 1m bar index we last processed
    last_1m_idx = 0
    # Signal from bar k fires at CLOSE of bar k → enter at OPEN of bar k+1
    pending_signal = 0
    pending_atr = float("nan")

    rows_15m = df_15m.reset_index(drop=True)

    for k in range(len(rows_15m)):
        bar_15m = rows_15m.iloc[k]

        # The next 15m bar's open_time = first 1m bar to process
        if k + 1 < len(rows_15m):
            next_15m_open = rows_15m.iloc[k + 1]["open_time"]
        else:
            next_15m_open = None

        # Find 1m index range: 1m bars that fall inside 15m bar k
        end_1m_idx = time_to_1m.get(next_15m_open, len(df_1m)) if next_15m_open is not None else len(df_1m)

        for i in range(last_1m_idx, end_1m_idx):
            row_1m = df_1m.iloc[i]
            bar_open = float(row_1m["open"])
            bar_high = float(row_1m["high"])
            bar_low = float(row_1m["low"])
            bar_time = row_1m["open_time"]

            # Check SL/TP on open trade
            if open_trade is not None:
                exit_price, exit_reason = _check_exit(open_trade, bar_high, bar_low)
                if exit_price is not None:
                    pnl = _calc_pnl(open_trade, exit_price, taker_fee)
                    balance += pnl
                    open_trade.exit_bar = i
                    open_trade.exit_time = bar_time
                    open_trade.exit_price = exit_price
                    open_trade.exit_reason = exit_reason
                    open_trade.pnl = pnl
                    trades.append(open_trade)
                    open_trade = None

            equity.append(balance)

            # Entry: pending_signal from previous 15m bar → enter at FIRST 1m bar here
            if i == last_1m_idx and pending_signal != 0 and open_trade is None:
                if not (math.isnan(pending_atr) or pending_atr <= 0):
                    qty = _calc_qty(balance, config, bar_open)
                    if qty > 0:
                        balance -= bar_open * qty * taker_fee
                        if pending_signal == 1:
                            open_trade = Trade(
                                entry_bar=i, entry_time=bar_time, entry_price=bar_open,
                                side="LONG", qty=qty,
                                sl_price=bar_open - config.sl_atr_mult * pending_atr,
                                tp_price=bar_open + config.tp_atr_mult * pending_atr,
                            )
                        else:
                            open_trade = Trade(
                                entry_bar=i, entry_time=bar_time, entry_price=bar_open,
                                side="SHORT", qty=qty,
                                sl_price=bar_open + config.sl_atr_mult * pending_atr,
                                tp_price=bar_open - config.tp_atr_mult * pending_atr,
                            )

        # Signal fires at CLOSE of this 15m bar → becomes pending for next period
        pending_signal = int(bar_15m["signal"])
        pending_atr = float(bar_15m["atr"])
        last_1m_idx = end_1m_idx

    # Force-close at last 1m bar
    if open_trade is not None:
        last = df_1m.iloc[-1]
        exit_price = float(last["close"])
        pnl = _calc_pnl(open_trade, exit_price, taker_fee)
        balance += pnl
        open_trade.exit_bar = len(df_1m) - 1
        open_trade.exit_time = last["open_time"]
        open_trade.exit_price = exit_price
        open_trade.exit_reason = "END"
        open_trade.pnl = pnl
        trades.append(open_trade)

    equity_curve = pd.Series(equity, index=df_1m["open_time"].iloc[:len(equity)], name="equity")
    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        starting_balance=starting_balance,
        final_balance=balance,
    )


def _check_exit(
    trade: Trade, bar_high: float, bar_low: float
) -> tuple[float | None, str | None]:
    if trade.side == "LONG":
        if bar_low <= trade.sl_price:
            return trade.sl_price, "SL"
        if bar_high >= trade.tp_price:
            return trade.tp_price, "TP"
    else:
        if bar_high >= trade.sl_price:
            return trade.sl_price, "SL"
        if bar_low <= trade.tp_price:
            return trade.tp_price, "TP"
    return None, None


def _calc_qty(balance: float, config: EmaCrossConfig, entry_price: float) -> float:
    notional = balance * config.margin_pct * config.leverage
    scale = 10 ** config.size_precision
    return math.floor(notional / entry_price * scale) / scale


def _calc_pnl(trade: Trade, exit_price: float, taker_fee: float) -> float:
    fee = exit_price * trade.qty * taker_fee
    if trade.side == "LONG":
        return (exit_price - trade.entry_price) * trade.qty - fee
    return (trade.entry_price - exit_price) * trade.qty - fee
