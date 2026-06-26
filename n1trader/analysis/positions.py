"""Convert Nautilus backtest fill/position reports to a normalised DataFrame."""
from __future__ import annotations

import pandas as pd


POSITION_COLS = [
    "entry_time",
    "exit_time",
    "side",
    "entry_price",
    "exit_price",
    "initial_sl",
    "size",
    "pnl_gross",
    "fees",
    "pnl_net",
    "bars_held",
]


def positions_from_reports(
    fills_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    initial_sl_map: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Build a normalised position records DataFrame from Nautilus report DataFrames.

    Parameters
    ----------
    fills_df:
        Output of BacktestEngine.trader.generate_order_fills_report().
    positions_df:
        Output of BacktestEngine.trader.generate_positions_report().
    initial_sl_map:
        Optional mapping {position_id: initial_sl_price} injected by the strategy.
        Comes from EmaCrossStrategy._initial_sl stored per trade.
    """
    if positions_df.empty:
        return pd.DataFrame(columns=POSITION_COLS)

    records = []
    for _, pos_row in positions_df.iterrows():
        pos_id = str(pos_row.get("position_id", ""))
        side_str = str(pos_row.get("side", "")).upper()

        # Normalise side to "LONG" / "SHORT"
        if "BUY" in side_str or "LONG" in side_str:
            side = "LONG"
        else:
            side = "SHORT"

        entry_price = float(pos_row.get("avg_px_open", 0))
        exit_price = float(pos_row.get("avg_px_close", 0))
        size = float(pos_row.get("quantity", pos_row.get("peak_qty", 0)))
        realized_pnl = float(pos_row.get("realized_pnl", 0))

        # Entry / exit timestamps
        entry_time = pd.to_datetime(pos_row.get("ts_opened", pd.NaT), utc=True)
        exit_time = pd.to_datetime(pos_row.get("ts_closed", pd.NaT), utc=True)

        # Fees: sum fills attributed to this position
        pos_fees = 0.0
        if not fills_df.empty and "commission" in fills_df.columns:
            mask = fills_df.get("position_id", fills_df.index) == pos_id
            pos_fees = fills_df.loc[mask, "commission"].astype(float).sum()

        pnl_gross = realized_pnl + pos_fees  # gross = net + fees re-added
        pnl_net = realized_pnl

        bars_held: int | None = None
        if pd.notna(entry_time) and pd.notna(exit_time):
            delta = exit_time - entry_time
            bars_held = int(delta.total_seconds() // 60)

        initial_sl = (initial_sl_map or {}).get(pos_id)

        records.append({
            "entry_time": entry_time,
            "exit_time": exit_time,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "initial_sl": initial_sl,
            "size": size,
            "pnl_gross": pnl_gross,
            "fees": pos_fees,
            "pnl_net": pnl_net,
            "bars_held": bars_held,
        })

    df = pd.DataFrame(records, columns=POSITION_COLS)
    return df
