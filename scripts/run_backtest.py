"""Full pipeline: download → signals → backtest → HTML report.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --symbol BTCUSDT --interval 15m
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from n1trading.backtest.engine import run_backtest
from n1trading.data.fetcher import fetch_futures_ohlcv
from n1trading.report.dashboard import generate_html_report
from n1trading.strategy.ema_cross import EmaCrossConfig, generate_signals

CONFIG = EmaCrossConfig(
    fast_period=12,
    slow_period=26,
    atr_period=14,
    sl_atr_mult=1.5,
    tp_atr_mult=2.5,
    margin_pct=0.05,
    leverage=20,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="ETHUSDT")
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--start", default="1 Jan, 2025")
    parser.add_argument("--end", default=None)
    parser.add_argument("--balance", type=float, default=10_000.0)
    args = parser.parse_args()

    print(f"Step 1: Downloading {args.symbol} {args.interval} from Binance Futures …")
    df = fetch_futures_ohlcv(
        symbol=args.symbol,
        interval=args.interval,
        start=args.start,
        end=args.end,
    )
    if df.empty:
        sys.exit("ERROR: No data returned — check symbol/interval/connection.")
    print(f"  {len(df):,} bars  {df['open_time'].iloc[0]} → {df['open_time'].iloc[-1]}")

    print("Step 2: Computing EMA signals …")
    df = generate_signals(df, CONFIG)
    n_signals = (df["signal"] != 0).sum()
    print(f"  Signals: {n_signals} ({(df['signal']==1).sum()} LONG / {(df['signal']==-1).sum()} SHORT)")

    print("Step 3: Running backtest …")
    result = run_backtest(df, CONFIG, starting_balance=args.balance)

    print("Step 4: Writing HTML report …")
    report_path = PROJECT_ROOT / "reports" / f"backtest_{args.symbol}_{args.interval}.html"
    generate_html_report(result, report_path)

    sep = "=" * 55
    print(f"\n{sep}")
    print(f"  Symbol       : {args.symbol}  {args.interval}")
    print(f"  Bars         : {len(df):,}")
    print(f"  Trades       : {result.n_trades}")
    print(f"  Win rate     : {result.win_rate*100:.1f}%")
    print(f"  Net PnL      : {result.net_pnl:+.2f} USDT  ({result.return_pct:+.2f}%)")
    print(f"  Profit factor: {result.profit_factor:.2f}")
    print(f"  Max drawdown : {result.max_drawdown_pct:.1f}%")
    print(f"  Report       : {report_path}")
    print(sep)


if __name__ == "__main__":
    main()
