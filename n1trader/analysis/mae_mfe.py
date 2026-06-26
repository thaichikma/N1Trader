"""MAE / MFE / R computation from 1-minute bar data."""
from __future__ import annotations

import pandas as pd


def compute_mae_mfe(
    positions: pd.DataFrame,
    bars_df: pd.DataFrame,
) -> pd.DataFrame:
    """Add mae, mfe, and R columns to a positions DataFrame.

    Parameters
    ----------
    positions:
        Normalised position records with at least:
        entry_time, exit_time, side, entry_price, initial_sl, size, pnl_net.
    bars_df:
        1-minute OHLCV DataFrame with open_time (UTC), open, high, low, close.
        Must cover the full range of position hold periods.

    Returns
    -------
    positions DataFrame with mae, mfe, R columns added (in place copy).
    """
    bars_df = bars_df.copy()
    bars_df["open_time"] = pd.to_datetime(bars_df["open_time"], utc=True)
    bars_indexed = bars_df.set_index("open_time").sort_index()

    out = positions.copy()
    maes, mfes, rs = [], [], []

    for _, row in out.iterrows():
        entry_t = pd.to_datetime(row["entry_time"], utc=True)
        exit_t = pd.to_datetime(row["exit_time"], utc=True)
        side = str(row["side"]).upper()
        entry_px = float(row["entry_price"])
        initial_sl = row.get("initial_sl")
        pnl_net = float(row.get("pnl_net", 0))
        size = float(row.get("size", 1))

        # Slice bars in hold period
        mask = (bars_indexed.index >= entry_t) & (bars_indexed.index <= exit_t)
        hold_bars = bars_indexed.loc[mask]

        if hold_bars.empty:
            maes.append(float("nan"))
            mfes.append(float("nan"))
        else:
            lows = hold_bars["low"].astype(float)
            highs = hold_bars["high"].astype(float)
            if side == "LONG":
                # MAE: worst adverse move below entry (positive = loss)
                mae = max(0.0, entry_px - lows.min())
                mfe = max(0.0, highs.max() - entry_px)
            else:
                mae = max(0.0, highs.max() - entry_px)
                mfe = max(0.0, entry_px - lows.min())
            maes.append(mae)
            mfes.append(mfe)

        # R = pnl_net / risk_per_unit; risk = |entry - initial_sl| * size
        if initial_sl is not None and size > 0:
            risk_per_unit = abs(entry_px - float(initial_sl))
            risk = risk_per_unit * size
            r_val = pnl_net / risk if risk > 0 else float("nan")
        else:
            r_val = float("nan")
        rs.append(r_val)

    out["mae"] = maes
    out["mfe"] = mfes
    out["R"] = rs
    out["win"] = out["pnl_net"] > 0
    return out
