#!/usr/bin/env python3
"""Run EMA Cross backtest on ETHUSDT-PERP 1m data (2025-01 → today).

Steps:
  1. Download monthly ZIPs from binance.vision (2025-01 → 2026-05)
  2. Gap-fill recent bars via ccxt (2026-06 → now)
  3. Load into Nautilus ParquetDataCatalog
  4. Run EmaCrossStrategy (EMA 12/26 + ATR SL/TP)
  5. Print results
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from n1trader.data.catalog import load_to_catalog, query_bars
from n1trader.data.downloader import download_bulk, gap_fill_with_ccxt, merge_parquets
from n1trader.data.news_windows import load_news_windows
from n1trader.engine.runner import run_backtest
from n1trader.engine.venue import make_eth_perp_instrument
from n1trader.strategy.ema_cross import EmaCrossConfig, EmaCrossStrategy

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CATALOG_DIR = DATA_DIR / "catalog"
NEWS_CSV = DATA_DIR / "news.csv"
SAMPLE_NEWS = PROJECT_ROOT / "tests" / "fixtures" / "news_sample.csv"

# Download range: monthly complete months
START_YEAR, START_MONTH = 2025, 1
END_YEAR, END_MONTH = 2026, 5   # last fully published month on binance.vision


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Download ─────────────────────────────────────────────────────────────
    print("Step 1: Downloading ETHUSDT-PERP 1m data from binance.vision …")
    paths = download_bulk(
        symbol="ETHUSDT",
        interval="1m",
        start_year=START_YEAR,
        start_month=START_MONTH,
        end_year=END_YEAR,
        end_month=END_MONTH,
        dest_dir=RAW_DIR,
    )
    print(f"  {len(paths)} monthly file(s) available")

    # ── 2. Merge + gap-fill ──────────────────────────────────────────────────────
    print("Step 2: Merging parquets and gap-filling via ccxt …")
    df = merge_parquets(paths)
    if df.empty:
        sys.exit("ERROR: No data downloaded — check internet connection.")
    print(f"  Merged: {len(df):,} bars  last={df['open_time'].max()}")

    df = gap_fill_with_ccxt(df, symbol="ETH/USDT:USDT")
    print(f"  After gap-fill: {len(df):,} bars  last={df['open_time'].max()}")

    # ── 3. Load catalog ──────────────────────────────────────────────────────────
    print("Step 3: Writing Nautilus catalog …")
    instrument = make_eth_perp_instrument()
    load_to_catalog(df, CATALOG_DIR, instrument=instrument)
    print(f"  Catalog → {CATALOG_DIR}")

    # ── 4. Run backtest ──────────────────────────────────────────────────────────
    print("Step 4: Loading bars and running backtest …")
    bars = query_bars(CATALOG_DIR)
    print(f"  Bars loaded: {len(bars):,}")

    news_path = NEWS_CSV if NEWS_CSV.exists() else SAMPLE_NEWS
    blackout_windows, cancel_marks = load_news_windows(
        str(news_path), impact_filter="HIGH"
    )
    print(f"  News HIGH-impact windows: {len(blackout_windows)}")

    config = EmaCrossConfig(
        strategy_id="EMA-CROSS-001",
        instrument_id_str="ETHUSDT-PERP.BINANCE",
        bar_type_str="ETHUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        fast_period=12,
        slow_period=26,
        atr_period=14,
        sl_atr_mult=1.5,
        tp_atr_mult=2.5,
        margin_pct=0.05,
        leverage=20,
    )
    strategy = EmaCrossStrategy(config)
    strategy.set_blackout_windows(blackout_windows, cancel_marks)

    result = run_backtest(bars, strategy, starting_balance=10_000.0)

    # ── 5. Results ───────────────────────────────────────────────────────────────
    _print_results(result)


def _print_results(result) -> None:
    import pandas as pd

    sep = "=" * 70
    print(f"\n{sep}")
    print("BACKTEST RESULTS — EMA Cross 12/26  SL=1.5×ATR  TP=2.5×ATR")
    print(sep)

    # Final account balance (last row where reported=True or just last row)
    acc = result.account
    if not acc.empty:
        reported = acc[acc.get("reported", pd.Series(False, index=acc.index)).astype(bool)]
        final_row = reported.iloc[-1] if not reported.empty else acc.iloc[-1]
        start = 10_000.0
        end = float(str(final_row.get("total", final_row.iloc[0])).replace(",", "").replace("_", ""))
        pnl = end - start
        ret_pct = pnl / start * 100
        print(f"\n  Starting balance : {start:>12,.2f} USDT")
        print(f"  Final balance    : {end:>12,.2f} USDT")
        print(f"  Net PnL          : {pnl:>+12,.2f} USDT  ({ret_pct:+.2f}%)")

    pos = result.positions
    fills = result.fills
    n_pos = len(pos)
    n_fills = len(fills)
    print(f"\n  Closed positions : {n_pos}")
    print(f"  Total fills      : {n_fills}")

    if not pos.empty:
        pnl_col = next((c for c in ["realized_pnl", "pnl"] if c in pos.columns), None)
        if pnl_col:
            pnl_vals = pos[pnl_col].astype(str).str.replace("_", "").str.split().str[0].astype(float)
            winners = (pnl_vals > 0).sum()
            losers  = (pnl_vals < 0).sum()
            avg_win = pnl_vals[pnl_vals > 0].mean() if winners else 0.0
            avg_los = pnl_vals[pnl_vals < 0].mean() if losers  else 0.0
            win_rate = winners / n_pos * 100 if n_pos else 0.0
            print(f"  Win rate         : {winners}/{n_pos}  ({win_rate:.1f}%)")
            print(f"  Avg win          : {avg_win:>+.4f} USDT")
            print(f"  Avg loss         : {avg_los:>+.4f} USDT")

        print(f"\n── All positions ──")
        show_cols = [c for c in [
            "instrument_id", "entry", "avg_px_open", "avg_px_close",
            "realized_pnl", "duration"
        ] if c in pos.columns]
        print(pos[show_cols].to_string(index=False) if show_cols else pos.to_string(index=False))

    if not fills.empty:
        print(f"\n── Last 10 fills ──")
        show = [c for c in ["ts_event", "side", "last_qty", "last_px", "commission"] if c in fills.columns]
        print(fills[show].tail(10).to_string(index=False) if show else fills.tail(10).to_string(index=False))

    print(f"\n{sep}")


if __name__ == "__main__":
    main()
