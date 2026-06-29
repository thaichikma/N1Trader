"""MTF backtest: signal on 15m, entry + SL/TP monitoring on 1m.

Usage:
    python scripts/run_backtest_mtf.py
    python scripts/run_backtest_mtf.py --symbol BTCUSDT --start "1 Jun, 2025"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from n1trading.backtest.engine import run_backtest_mtf
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
    parser.add_argument("--start", default="1 Jan, 2025")
    parser.add_argument("--end", default=None)
    parser.add_argument("--balance", type=float, default=10_000.0)
    args = parser.parse_args()

    print(f"Step 1: Downloading {args.symbol} 15m (signals) …")
    df_15m = fetch_futures_ohlcv(args.symbol, "15m", args.start, args.end)
    print(f"  {len(df_15m):,} bars  {df_15m['open_time'].iloc[0]} → {df_15m['open_time'].iloc[-1]}")

    print(f"Step 2: Downloading {args.symbol} 1m (execution) …")
    df_1m = fetch_futures_ohlcv(args.symbol, "1m", args.start, args.end)
    print(f"  {len(df_1m):,} bars")

    print("Step 3: Computing 15m signals …")
    df_15m = generate_signals(df_15m, CONFIG)
    n_sig = (df_15m["signal"] != 0).sum()
    print(f"  Signals: {n_sig}  ({(df_15m['signal']==1).sum()} LONG / {(df_15m['signal']==-1).sum()} SHORT)")

    print("Step 4: Running MTF backtest …")
    result = run_backtest_mtf(df_15m, df_1m, CONFIG, starting_balance=args.balance)

    print("Step 5: Writing HTML report …")
    report_path = PROJECT_ROOT / "reports" / f"backtest_{args.symbol}_mtf_15m1m.html"
    generate_html_report(
        result, report_path,
        title=f"EMA Cross 12/26 MTF (15m signal / 1m exec) — {args.symbol}"
    )

    sep = "=" * 55
    print(f"\n{sep}")
    print(f"  Symbol       : {args.symbol}  15m signal / 1m exec")
    print(f"  Trades       : {result.n_trades}")
    print(f"  Win rate     : {result.win_rate*100:.1f}%")
    print(f"  Net PnL      : {result.net_pnl:+.2f} USDT  ({result.return_pct:+.2f}%)")
    print(f"  Profit factor: {result.profit_factor:.2f}")
    print(f"  Max drawdown : {result.max_drawdown_pct:.1f}%")
    print(f"  Report       : {report_path}")
    print(sep)


if __name__ == "__main__":
    main()
