"""Walk-forward search harness: train/select/test loop with optional parallelism.

Memory model
------------
Sequential (max_workers=1, default):
    All work runs in the main process.  GC reclaims each BacktestEngine's
    Rust-side memory between param evaluations.  Safest option.

Parallel (max_workers > 1):
    bars_df is written into OS shared memory ONCE.  A single ProcessPoolExecutor
    lives for the entire walk-forward run — workers import nautilus_trader once,
    not once per window.  Each task receives only three scalars
    (train_start_ns, train_end_ns, param); no DataFrame is pickled per task.
"""
from __future__ import annotations

import gc
import logging
import multiprocessing.shared_memory as _shm_mod
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from n1trader.optimize.grid import ParamSet, generate_grid
from n1trader.optimize.metrics import score_params
from n1trader.optimize.windows import WFWindow, make_windows, slice_bars

logger = logging.getLogger(__name__)

RunFn = Callable[[pd.DataFrame, ParamSet], pd.Series]


# ── Public data classes ─────────────────────────────────────────────────────────

@dataclass
class ISResult:
    param: ParamSet
    score: float


@dataclass
class WFWindowResult:
    window: WFWindow
    best_param: ParamSet
    is_score: float
    oos_pnl: pd.Series
    oos_score: float


# ── Shared-memory bundle ────────────────────────────────────────────────────────

class _ShmBundle:
    """Puts bars_df into two shared-memory segments (timestamps + OHLCV).

    Workers attach to these segments without copying data.
    Call close_and_unlink() when done to release OS resources.
    """

    _OHLCV_COLS = ("open", "high", "low", "close", "volume")

    def __init__(self, df: pd.DataFrame) -> None:
        ts = pd.to_datetime(df["open_time"], utc=True).astype("int64").to_numpy()
        ohlcv = df[list(self._OHLCV_COLS)].to_numpy(dtype=np.float64)

        self._ts_shm = _shm_mod.SharedMemory(create=True, size=ts.nbytes)
        np.ndarray(ts.shape, dtype=ts.dtype, buffer=self._ts_shm.buf)[:] = ts

        self._ohlcv_shm = _shm_mod.SharedMemory(create=True, size=ohlcv.nbytes)
        np.ndarray(ohlcv.shape, dtype=ohlcv.dtype, buffer=self._ohlcv_shm.buf)[:] = ohlcv

        # Metadata passed to workers via pool initializer (tiny, safe to pickle).
        self.ts_name: str = self._ts_shm.name
        self.ohlcv_name: str = self._ohlcv_shm.name
        self.nrows: int = len(df)
        self.ohlcv_shape: tuple[int, int] = ohlcv.shape

    def close_and_unlink(self) -> None:
        for shm in (self._ts_shm, self._ohlcv_shm):
            try:
                shm.close()
                shm.unlink()
            except Exception:
                pass


# ── Worker-process globals (set once by _worker_init) ──────────────────────────

_W_TS: np.ndarray | None = None       # int64 ns timestamps, shape (N,)
_W_OHLCV: np.ndarray | None = None    # float64 OHLCV, shape (N, 5)
_W_SHM: list = []                     # open SharedMemory handles (keep-alive)
_W_RUN_FN: RunFn | None = None
_W_METRIC: str = "expectancy"


def _worker_init(
    ts_name: str,
    ohlcv_name: str,
    nrows: int,
    ohlcv_shape: tuple[int, int],
    run_fn: RunFn,
    metric: str,
) -> None:
    """Attach to shared-memory segments once per worker process."""
    global _W_TS, _W_OHLCV, _W_SHM, _W_RUN_FN, _W_METRIC
    ts_shm = _shm_mod.SharedMemory(name=ts_name)
    ohlcv_shm = _shm_mod.SharedMemory(name=ohlcv_name)
    _W_TS = np.ndarray((nrows,), dtype=np.int64, buffer=ts_shm.buf)
    _W_OHLCV = np.ndarray(ohlcv_shape, dtype=np.float64, buffer=ohlcv_shm.buf)
    _W_SHM = [ts_shm, ohlcv_shm]
    _W_RUN_FN = run_fn
    _W_METRIC = metric


def _worker_eval(
    train_start_ns: int, train_end_ns: int, param: ParamSet
) -> tuple[ParamSet, float]:
    """Slice the shared dataset, run run_fn, return (param, score).

    Only three small scalars are pickled per task — no DataFrame transfer.
    """
    mask = (_W_TS >= train_start_ns) & (_W_TS <= train_end_ns)
    train_df = pd.DataFrame({
        "open_time": pd.to_datetime(_W_TS[mask], unit="ns", utc=True),
        "open":   _W_OHLCV[mask, 0],
        "high":   _W_OHLCV[mask, 1],
        "low":    _W_OHLCV[mask, 2],
        "close":  _W_OHLCV[mask, 3],
        "volume": _W_OHLCV[mask, 4],
    })
    pnl = _W_RUN_FN(train_df, param)
    score = score_params(pnl, _W_METRIC)
    del train_df, pnl
    gc.collect()
    return param, score


# ── Sequential helpers ──────────────────────────────────────────────────────────

def _run_single(
    bars_df: pd.DataFrame, param: ParamSet, run_fn: RunFn
) -> tuple[ParamSet, pd.Series]:
    pnl = run_fn(bars_df, param)
    return param, pnl


def _eval_grid_sequential(
    train_bars: pd.DataFrame,
    grid: list[ParamSet],
    run_fn: RunFn,
    metric: str,
) -> ISResult | None:
    best: ISResult | None = None
    for param in grid:
        try:
            pnl = run_fn(train_bars, param)
            score = score_params(pnl, metric)
            if best is None or score > best.score:
                best = ISResult(param=param, score=score)
        except Exception as exc:
            logger.warning("Grid run failed: %s", exc)
        else:
            del pnl
            gc.collect()
    return best


# ── Public API ──────────────────────────────────────────────────────────────────

def search_window(
    train_bars: pd.DataFrame,
    test_bars: pd.DataFrame,
    grid: list[ParamSet],
    run_fn: RunFn,
    metric: str = "expectancy",
) -> WFWindowResult | None:
    """Evaluate all grid combinations on train; pick best; test on OOS.

    Runs sequentially in the caller's process.  Use run_walk_forward for
    the full multi-window search with optional parallelism.
    """
    if train_bars.empty or not grid:
        return None

    best = _eval_grid_sequential(train_bars, grid, run_fn, metric)
    if best is None:
        return None

    logger.info("Best IS param: %s score=%.4f", best.param.label(), best.score)
    _, oos_pnl = _run_single(test_bars, best.param, run_fn)
    oos_score = score_params(oos_pnl, metric)

    dummy_window = WFWindow(
        train_start=pd.Timestamp("1970-01-01", tz="UTC"),
        train_end=pd.Timestamp("1970-01-01", tz="UTC"),
        test_start=pd.Timestamp("1970-01-01", tz="UTC"),
        test_end=pd.Timestamp("1970-01-01", tz="UTC"),
    )
    return WFWindowResult(
        window=dummy_window,
        best_param=best.param,
        is_score=best.score,
        oos_pnl=oos_pnl,
        oos_score=oos_score,
    )


def run_walk_forward(
    bars_df: pd.DataFrame,
    run_fn: RunFn,
    train_bars: int = 20_160,
    test_bars: int = 10_080,
    metric: str = "expectancy",
    max_workers: int = 1,
    anchored: bool = False,
    dest_path: str | Path | None = None,
    grid: list[ParamSet] | None = None,
) -> pd.DataFrame:
    """Full walk-forward search.  Returns IS/OOS summary DataFrame.

    Parameters
    ----------
    max_workers:
        1 (default) — sequential; safest, lowest peak RAM.
        >1          — parallel via shared-memory pool; workers import
                      nautilus_trader once for the entire run.
    """
    if grid is None:
        grid = generate_grid()

    ts = pd.to_datetime(bars_df["open_time"], utc=True)
    windows = make_windows(
        start=ts.min(),
        end=ts.max(),
        train_bars=train_bars,
        test_bars=test_bars,
        anchored=anchored,
    )
    logger.info("Walk-forward: %d windows, grid size=%d", len(windows), len(grid))

    rows: list[dict] = []

    if max_workers <= 1:
        rows = _run_sequential(bars_df, windows, grid, run_fn, metric)
    else:
        rows = _run_parallel(bars_df, windows, grid, run_fn, metric, max_workers)

    summary = pd.DataFrame(rows)

    if dest_path is not None and not summary.empty:
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        summary.to_parquet(dest_path, index=False)
        logger.info("Walk-forward summary written to %s", dest_path)

    return summary


# ── Internal run paths ──────────────────────────────────────────────────────────

def _run_sequential(
    bars_df: pd.DataFrame,
    windows: list[WFWindow],
    grid: list[ParamSet],
    run_fn: RunFn,
    metric: str,
) -> list[dict]:
    rows: list[dict] = []
    for i, win in enumerate(windows):
        _log_win(i, len(windows), win)
        train = slice_bars(bars_df, win.train_start, win.train_end)
        test = slice_bars(bars_df, win.test_start, win.test_end)
        result = search_window(train, test, grid, run_fn, metric)
        if result is None:
            continue
        result.window = win
        rows.append(_to_row(i + 1, win, result))
    return rows


def _run_parallel(
    bars_df: pd.DataFrame,
    windows: list[WFWindow],
    grid: list[ParamSet],
    run_fn: RunFn,
    metric: str,
    max_workers: int,
) -> list[dict]:
    """One persistent pool; full bars_df in shared memory; no per-task pickling."""
    bundle = _ShmBundle(bars_df)
    rows: list[dict] = []
    try:
        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_worker_init,
            initargs=(
                bundle.ts_name, bundle.ohlcv_name,
                bundle.nrows, bundle.ohlcv_shape,
                run_fn, metric,
            ),
        ) as pool:
            for i, win in enumerate(windows):
                _log_win(i, len(windows), win)
                test = slice_bars(bars_df, win.test_start, win.test_end)
                start_ns = int(win.train_start.value)
                end_ns = int(win.train_end.value)

                futures = {
                    pool.submit(_worker_eval, start_ns, end_ns, p): p
                    for p in grid
                }
                best: ISResult | None = None
                for fut in as_completed(futures):
                    try:
                        param, score = fut.result()
                        if best is None or score > best.score:
                            best = ISResult(param=param, score=score)
                    except Exception as exc:
                        logger.warning("Grid task failed: %s", exc)

                if best is None:
                    continue
                logger.info("Best IS param: %s score=%.4f", best.param.label(), best.score)
                _, oos_pnl = _run_single(test, best.param, run_fn)
                oos_score = score_params(oos_pnl, metric)
                result = WFWindowResult(
                    window=win,
                    best_param=best.param,
                    is_score=best.score,
                    oos_pnl=oos_pnl,
                    oos_score=oos_score,
                )
                rows.append(_to_row(i + 1, win, result))
    finally:
        bundle.close_and_unlink()
    return rows


def _log_win(i: int, total: int, win: WFWindow) -> None:
    logger.info(
        "Window %d/%d IS=%s→%s OOS=%s→%s",
        i + 1, total,
        win.train_start.date(), win.train_end.date(),
        win.test_start.date(), win.test_end.date(),
    )


def _to_row(idx: int, win: WFWindow, result: WFWindowResult) -> dict:
    return {
        "window": idx,
        "train_start": win.train_start,
        "train_end": win.train_end,
        "test_start": win.test_start,
        "test_end": win.test_end,
        "best_param": result.best_param.label(),
        "is_score": result.is_score,
        "oos_score": result.oos_score,
        "oos_trades": len(result.oos_pnl),
    }
