from __future__ import annotations

import html
from typing import Iterable

from .nse_client import StockMove
from .reason_metadata import ReasonMeta


def format_reason_style_message(
    trade_date: str,
    movers: Iterable[StockMove],
    reasons_by_symbol: dict[str, str],
    reason_meta_by_symbol: dict[str, ReasonMeta] | None = None,
) -> str:
    lines: list[str] = [f"📈 <b>NSE Movers Reason Summary ({html.escape(trade_date)})</b>"]

    for mover in movers:
        symbol = html.escape(mover.symbol)
        pct = f"{mover.percent_change:+.2f}%"
        reason = html.escape(reasons_by_symbol.get(mover.symbol, "No clear reason found."))
        meta = (reason_meta_by_symbol or {}).get(mover.symbol)
        lines.append("")
        lines.append(f"<b>{symbol} {pct}</b>")
        if meta:
            lines.append(f"Confidence: <b>{meta.confidence}%</b>")
        lines.append("Reason:")
        lines.append(reason)
        if meta and meta.evidence_urls:
            links = []
            for idx, url in enumerate(meta.evidence_urls[:2], start=1):
                links.append(f'<a href="{html.escape(url, quote=True)}">src{idx}</a>')
            lines.append(f"Evidence: {' | '.join(links)}")

    return "\n".join(lines)
