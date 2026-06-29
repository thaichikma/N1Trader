"""Generate a self-contained HTML backtest report (no external dependencies)."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from n1trading.backtest.engine import BacktestResult


def generate_html_report(
    result: BacktestResult,
    output_path: Path,
    title: str = "EMA Cross 12/26 — Backtest Report",
) -> None:
    """Write a self-contained HTML report to output_path."""
    equity_chart = _equity_chart(result)
    monthly_chart = _monthly_pnl_chart(result)
    trade_rows = _trade_table_rows(result)

    sign = "+" if result.net_pnl >= 0 else ""
    pf = result.profit_factor
    pf_str = f"{pf:.2f}" if pf != float("inf") else "∞"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #0f1117; color: #e0e0e0; margin: 0; padding: 24px; }}
  h1   {{ color: #fff; font-size: 1.4rem; margin-bottom: 4px; }}
  .sub {{ color: #888; font-size: 0.85rem; margin-bottom: 24px; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 28px; }}
  .card {{ background: #1a1d27; border-radius: 8px; padding: 16px 20px; min-width: 140px; }}
  .card .label {{ font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: .05em; }}
  .card .value {{ font-size: 1.4rem; font-weight: 600; margin-top: 4px; }}
  .pos {{ color: #26c281; }} .neg {{ color: #e05252; }} .neu {{ color: #e0e0e0; }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{ font-size: 1rem; color: #aaa; border-bottom: 1px solid #2a2d3a;
                 padding-bottom: 6px; margin-bottom: 16px; }}
  img {{ max-width: 100%; border-radius: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: #1a1d27; color: #888; text-align: left; padding: 8px 10px;
        font-weight: 500; text-transform: uppercase; font-size: 0.72rem; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #1a1d27; }}
  tr:hover td {{ background: #1a1d27; }}
  .long {{ color: #26c281; }} .short {{ color: #e05252; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="sub">ETHUSDT USDⓈ-M Futures · 1m · SL 1.5×ATR · TP 2.5×ATR · 5% margin · 20× leverage</p>

<div class="stats">
  {_card("Starting", f"10,000.00 USDT", "neu")}
  {_card("Final", f"{result.final_balance:,.2f} USDT", "pos" if result.net_pnl >= 0 else "neg")}
  {_card("Net PnL", f"{sign}{result.net_pnl:,.2f} USDT ({sign}{result.return_pct:.1f}%)", "pos" if result.net_pnl >= 0 else "neg")}
  {_card("Trades", str(result.n_trades), "neu")}
  {_card("Win Rate", f"{result.win_rate*100:.1f}%", "neu")}
  {_card("Profit Factor", pf_str, "pos" if pf > 1 else "neg")}
  {_card("Max Drawdown", f"{result.max_drawdown_pct:.1f}%", "neg")}
  {_card("Avg Win", f"+{result.avg_win:.2f} USDT", "pos")}
  {_card("Avg Loss", f"{result.avg_loss:.2f} USDT", "neg")}
</div>

<div class="section">
  <h2>Equity Curve &amp; Drawdown</h2>
  <img src="data:image/png;base64,{equity_chart}" alt="equity curve">
</div>

<div class="section">
  <h2>Monthly PnL</h2>
  <img src="data:image/png;base64,{monthly_chart}" alt="monthly pnl">
</div>

<div class="section">
  <h2>Trades (last 100)</h2>
  <table>
    <thead>
      <tr>
        <th>Entry Time</th><th>Side</th><th>Entry</th>
        <th>Exit</th><th>Exit Reason</th><th>PnL (USDT)</th>
      </tr>
    </thead>
    <tbody>
      {trade_rows}
    </tbody>
  </table>
</div>
</body>
</html>"""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def _card(label: str, value: str, cls: str) -> str:
    return f'<div class="card"><div class="label">{label}</div><div class="value {cls}">{value}</div></div>'


def _equity_chart(result: BacktestResult) -> str:
    equity = result.equity_curve
    peak = equity.cummax()
    drawdown = (equity - peak) / peak * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), facecolor="#0f1117",
                                    gridspec_kw={"height_ratios": [3, 1]})
    fig.subplots_adjust(hspace=0.05)

    for ax in (ax1, ax2):
        ax.set_facecolor("#0f1117")
        ax.tick_params(colors="#888", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#2a2d3a")

    ax1.plot(equity.index, equity.values, color="#26c281", linewidth=1.2)
    ax1.fill_between(equity.index, result.starting_balance, equity.values,
                     where=equity.values >= result.starting_balance,
                     alpha=0.15, color="#26c281")
    ax1.fill_between(equity.index, result.starting_balance, equity.values,
                     where=equity.values < result.starting_balance,
                     alpha=0.15, color="#e05252")
    ax1.axhline(result.starting_balance, color="#444", linewidth=0.8, linestyle="--")
    ax1.set_ylabel("Equity (USDT)", color="#888", fontsize=8)
    ax1.xaxis.set_visible(False)
    ax1.yaxis.label.set_color("#888")

    ax2.fill_between(drawdown.index, drawdown.values, 0, color="#e05252", alpha=0.6)
    ax2.set_ylabel("Drawdown %", color="#888", fontsize=8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")

    return _fig_to_b64(fig)


def _monthly_pnl_chart(result: BacktestResult) -> str:
    if not result.trades:
        fig, ax = plt.subplots(figsize=(12, 3), facecolor="#0f1117")
        ax.text(0.5, 0.5, "No trades", ha="center", va="center", color="#888")
        return _fig_to_b64(fig)

    records = [
        {"month": t.exit_time.to_period("M"), "pnl": t.pnl}
        for t in result.trades if t.exit_time and t.pnl is not None
    ]
    monthly = (
        pd.DataFrame(records)
        .groupby("month")["pnl"]
        .sum()
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(12, 3), facecolor="#0f1117")
    ax.set_facecolor("#0f1117")
    ax.tick_params(colors="#888", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#2a2d3a")

    colors = ["#26c281" if v >= 0 else "#e05252" for v in monthly.values]
    ax.bar(range(len(monthly)), monthly.values, color=colors, width=0.7)
    ax.axhline(0, color="#444", linewidth=0.8)
    ax.set_xticks(range(len(monthly)))
    ax.set_xticklabels([str(p) for p in monthly.index], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("PnL (USDT)", color="#888", fontsize=8)

    return _fig_to_b64(fig)


def _trade_table_rows(result: BacktestResult) -> str:
    rows = ""
    for t in result.trades[-100:]:
        side_cls = "long" if t.side == "LONG" else "short"
        pnl = t.pnl or 0.0
        pnl_cls = "pos" if pnl >= 0 else "neg"
        sign = "+" if pnl >= 0 else ""
        entry_str = t.entry_time.strftime("%Y-%m-%d %H:%M") if t.entry_time else "-"
        exit_str = f"{t.exit_price:.2f}" if t.exit_price is not None else "-"
        rows += (
            f"<tr>"
            f"<td>{entry_str}</td>"
            f'<td class="{side_cls}">{t.side}</td>'
            f"<td>{t.entry_price:.2f}</td>"
            f"<td>{exit_str}</td>"
            f"<td>{t.exit_reason or '-'}</td>"
            f'<td class="{pnl_cls}">{sign}{pnl:.4f}</td>'
            f"</tr>\n"
        )
    return rows


def _fig_to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()
