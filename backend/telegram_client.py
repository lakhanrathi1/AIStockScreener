from __future__ import annotations

import html
import logging
from typing import Iterable

import requests

from .config import Settings
from .nse_client import StockMove

logger = logging.getLogger(__name__)


class TelegramClient:
    """Tiny wrapper around the Telegram Bot API for sending text messages."""

    def __init__(self, settings: Settings) -> None:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set to send Telegram messages."
            )
        self._bot_token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"

    def send_text(self, text: str) -> None:
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            requests.post(f"{self._base_url}/sendMessage", data=payload, timeout=10)
            logger.info("Telegram message sent (%d chars)", len(text))
        except requests.RequestException:
            # For this MVP we ignore failures; you can log or alert later.
            logger.exception("Telegram send failed")
            return

    def send_movers_summary(
        self,
        trade_date: str,
        movers: Iterable[StockMove],
        reasons_by_symbol: dict[str, str],
    ) -> None:
        movers_list = list(movers)
        if not movers_list:
            self.send_text(f"No 5–10% movers found for {html.escape(trade_date)}.")
            return

        up_lines: list[str] = []
        down_lines: list[str] = []

        for m in movers_list:
            pct = f"{m.percent_change:.2f}%"
            reason = reasons_by_symbol.get(m.symbol, "")
            snippet_raw = reason[:220] + ("…" if len(reason) > 220 else "")
            snippet = html.escape(snippet_raw)
            symbol = html.escape(m.symbol)
            line = f"• <code>{symbol}</code> <b>{pct}</b> – {snippet}"
            if m.direction == "up":
                up_lines.append(f"{line} ⬆️")
            else:
                down_lines.append(f"{line} ⬇️")

        parts: list[str] = [f"📈 <b>AI Indian Stock Movers – {html.escape(trade_date)}</b>"]
        if up_lines:
            parts.append("")
            parts.append("📊 <b>Gainers (5–10% up)</b>")
            parts.extend(up_lines)
        if down_lines:
            parts.append("")
            parts.append("📉 <b>Losers (5–10% down)</b>")
            parts.extend(down_lines)

        full_text = "\n".join(parts)

        # Split into reasonably sized chunks without breaking formatting.
        lines = full_text.split("\n")
        chunks: list[str] = []
        current = ""
        for line in lines:
            candidate = (current + "\n" + line) if current else line
            if len(candidate) > 3500:
                chunks.append(current)
                current = line
            else:
                current = candidate
        if current:
            chunks.append(current)

        for chunk in chunks:
            self.send_text(chunk)
