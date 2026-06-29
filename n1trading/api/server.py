"""FastAPI backtest server: run backtests via REST API, serve the frontend."""
from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from n1trading.backtest.engine import run_backtest, run_backtest_mtf
from n1trading.data.fetcher import fetch_futures_ohlcv
from n1trading.strategy.ema_cross import EmaCrossConfig, generate_signals

_STATIC_DIR = Path(__file__).parent.parent / "static"
_executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title="N1Trading Backtest API", version="0.1.0")

# In-memory run store: run_id → serialized result dict
_runs: dict[str, dict] = {}


class BacktestRequest(BaseModel):
    symbol: str = "ETHUSDT"
    signal_interval: str = "15m"   # timeframe for EMA signal
    exec_interval: str = "1m"      # timeframe for entry/SL/TP execution
    start: str = "1 Jan, 2025"
    end: Optional[str] = None
    balance: float = 10_000.0
    # Strategy
    fast_period: int = 12
    slow_period: int = 26
    atr_period: int = 14
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.5
    leverage: int = 20
    margin_pct: float = 0.05
    # Filters
    adx_threshold: float = 20.0
    atr_min_pct: float = 0.002


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.post("/api/backtest")
async def run_backtest_endpoint(req: BacktestRequest):
    """Run a backtest. Blocks until complete (data is cached after first run)."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_executor, _execute_backtest, req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    _runs[result["id"]] = result
    return result


@app.get("/api/runs")
async def list_runs():
    """Return all run summaries (no equity/trade detail)."""
    return [_run_summary(r) for r in _runs.values()]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return _runs[run_id]


@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str):
    _runs.pop(run_id, None)
    return {"deleted": run_id}


# ── Static files + root ────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
async def frontend():
    return FileResponse(str(_STATIC_DIR / "index.html"))


# ── Backtest execution (runs in thread pool) ───────────────────────────────

def _execute_backtest(req: BacktestRequest) -> dict:
    config = EmaCrossConfig(
        fast_period=req.fast_period,
        slow_period=req.slow_period,
        atr_period=req.atr_period,
        sl_atr_mult=req.sl_atr_mult,
        tp_atr_mult=req.tp_atr_mult,
        leverage=req.leverage,
        margin_pct=req.margin_pct,
        adx_threshold=req.adx_threshold,
        atr_min_pct=req.atr_min_pct,
    )

    use_mtf = req.signal_interval != req.exec_interval

    df_signal = fetch_futures_ohlcv(req.symbol, req.signal_interval, req.start, req.end)
    df_signal = generate_signals(df_signal, config)

    if use_mtf:
        df_exec = fetch_futures_ohlcv(req.symbol, req.exec_interval, req.start, req.end)
        result = run_backtest_mtf(df_signal, df_exec, config, req.balance)
    else:
        result = run_backtest(df_signal, config, req.balance)

    run_id = uuid.uuid4().hex[:8]
    return {
        "id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "symbol": req.symbol,
            "signal_interval": req.signal_interval,
            "exec_interval": req.exec_interval,
            "start": req.start,
            "end": req.end,
            "balance": req.balance,
            "fast_period": req.fast_period,
            "slow_period": req.slow_period,
            "atr_period": req.atr_period,
            "sl_atr_mult": req.sl_atr_mult,
            "tp_atr_mult": req.tp_atr_mult,
            "leverage": req.leverage,
            "margin_pct": req.margin_pct,
            "adx_threshold": req.adx_threshold,
            "atr_min_pct": req.atr_min_pct,
        },
        "stats": {
            "n_trades": result.n_trades,
            "win_rate": round(result.win_rate * 100, 1),
            "net_pnl": round(result.net_pnl, 2),
            "return_pct": round(result.return_pct, 2),
            "profit_factor": round(result.profit_factor, 2) if result.profit_factor != float("inf") else 999,
            "max_drawdown_pct": round(result.max_drawdown_pct, 1),
            "avg_win": round(result.avg_win, 4),
            "avg_loss": round(result.avg_loss, 4),
            "final_balance": round(result.final_balance, 2),
        },
        "equity": _downsample_equity(result.equity_curve),
        "monthly": _monthly_pnl(result),
        "trades": _serialize_trades(result),
    }


def _downsample_equity(equity: pd.Series, n: int = 600) -> list[dict]:
    if len(equity) > n:
        step = max(1, len(equity) // n)
        equity = equity.iloc[::step]
    return [{"t": ts.isoformat(), "v": round(float(v), 2)} for ts, v in equity.items()]


def _monthly_pnl(result) -> list[dict]:
    import warnings
    if not result.trades:
        return []
    rows = [
        {"month": t.exit_time.to_period("M"), "pnl": t.pnl}
        for t in result.trades if t.exit_time and t.pnl is not None
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        monthly = (
            pd.DataFrame(rows).groupby("month")["pnl"].sum().sort_index()
        )
    return [{"month": str(p), "pnl": round(float(v), 2)} for p, v in monthly.items()]


def _serialize_trades(result) -> list[dict]:
    return [
        {
            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "side": t.side,
            "entry_price": round(t.entry_price, 2),
            "exit_price": round(t.exit_price, 2) if t.exit_price else None,
            "exit_reason": t.exit_reason,
            "qty": t.qty,
            "pnl": round(t.pnl, 4) if t.pnl is not None else None,
        }
        for t in result.trades
    ]


def _run_summary(run: dict) -> dict:
    return {k: run[k] for k in ("id", "created_at", "config", "stats")}
