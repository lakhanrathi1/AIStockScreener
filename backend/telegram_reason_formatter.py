from __future__ import annotations

import html
from typing import Iterable

from .nse_client import StockMove


def format_reason_style_message(
    trade_date: str,
    movers: Iterable[StockMove],
    reasons_by_symbol: dict[str, str],
) -> str:
    lines: list[str] = [f"📈 <b>NSE Movers Reason Summary ({html.escape(trade_date)})</b>"]

    for mover in movers:
        symbol = html.escape(mover.symbol)
        pct = f"{mover.percent_change:+.2f}%"
        reason = html.escape(reasons_by_symbol.get(mover.symbol, "No clear reason found."))
        lines.append("")
        lines.append(f"<b>{symbol} {pct}</b>")
        lines.append("Reason:")
        lines.append(reason)

    return "\n".join(lines)
