"""Walk-forward search harness: train/select/test loop with optional parallelism."""
from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from n1trader.optimize.grid import ParamSet, generate_grid
from n1trader.optimize.metrics import score_params
from n1trader.optimize.windows import WFWindow, make_windows, slice_bars

logger = logging.getLogger(__name__)

RunFn = Callable[[pd.DataFrame, ParamSet], pd.Series]

_POOL_TRAIN: pd.DataFrame | None = None
_POOL_RUN_FN: RunFn | None = None
_POOL_METRIC: str = "expectancy"


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


def _pool_init(train_bars: pd.DataFrame, run_fn: RunFn, metric: str) -> None:
    global _POOL_TRAIN, _POOL_RUN_FN, _POOL_METRIC
    _POOL_TRAIN = train_bars
    _POOL_RUN_FN = run_fn
    _POOL_METRIC = metric


def _pool_eval(param: ParamSet) -> tuple[ParamSet, float]:
    assert _POOL_TRAIN is not None and _POOL_RUN_FN is not None
    pnl = _POOL_RUN_FN(_POOL_TRAIN, param)
    return param, score_params(pnl, _POOL_METRIC)


def _run_single(
    bars_df: pd.DataFrame,
    param: ParamSet,
    run_fn: RunFn,
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
    return best


def _eval_grid_parallel(
    grid: list[ParamSet],
    executor: ProcessPoolExecutor,
) -> ISResult | None:
    best: ISResult | None = None
    futures = {executor.submit(_pool_eval, p): p for p in grid}
    for fut in as_completed(futures):
        try:
            param, score = fut.result()
            if best is None or score > best.score:
                best = ISResult(param=param, score=score)
        except Exception as exc:
            logger.warning("Grid run failed: %s", exc)
    return best


def search_window(
    train_bars: pd.DataFrame,
    test_bars: pd.DataFrame,
    grid: list[ParamSet],
    run_fn: RunFn,
    metric: str = "expectancy",
    executor: ProcessPoolExecutor | None = None,
    max_workers: int = 4,
) -> WFWindowResult | None:
    """Run all grid combinations on train, pick best, evaluate on test."""
    if train_bars.empty or not grid:
        return None

    own_pool = executor is None and max_workers > 1
    pool: ProcessPoolExecutor | None = None
    try:
        if max_workers <= 1:
            best = _eval_grid_sequential(train_bars, grid, run_fn, metric)
        else:
            if executor is None:
                pool = ProcessPoolExecutor(
                    max_workers=max_workers,
                    initializer=_pool_init,
                    initargs=(train_bars, run_fn, metric),
                )
                executor = pool
            best = _eval_grid_parallel(grid, executor)
    finally:
        if own_pool and pool is not None:
            pool.shutdown(wait=True)

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
    max_workers: int = 4,
    anchored: bool = False,
    dest_path: str | Path | None = None,
    grid: list[ParamSet] | None = None,
) -> pd.DataFrame:
    """Full walk-forward search. Returns IS/OOS summary DataFrame."""
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

    rows = []
    for i, win in enumerate(windows):
        logger.info(
            "Window %d/%d IS=%s→%s OOS=%s→%s",
            i + 1,
            len(windows),
            win.train_start.date(),
            win.train_end.date(),
            win.test_start.date(),
            win.test_end.date(),
        )
        train = slice_bars(bars_df, win.train_start, win.train_end)
        test = slice_bars(bars_df, win.test_start, win.test_end)

        # One process pool per window: each worker holds a single train slice copy.
        if max_workers > 1:
            with ProcessPoolExecutor(
                max_workers=max_workers,
                initializer=_pool_init,
                initargs=(train, run_fn, metric),
            ) as pool:
                result = search_window(
                    train, test, grid, run_fn, metric, executor=pool
                )
        else:
            result = search_window(
                train, test, grid, run_fn, metric, max_workers=1
            )

        if result is None:
            continue
        result.window = win
        rows.append({
            "window": i + 1,
            "train_start": win.train_start,
            "train_end": win.train_end,
            "test_start": win.test_start,
            "test_end": win.test_end,
            "best_param": result.best_param.label(),
            "is_score": result.is_score,
            "oos_score": result.oos_score,
            "oos_trades": len(result.oos_pnl),
        })

    summary = pd.DataFrame(rows)

    if dest_path is not None and not summary.empty:
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        summary.to_parquet(dest_path, index=False)
        logger.info("Walk-forward summary written to %s", dest_path)

    return summary
