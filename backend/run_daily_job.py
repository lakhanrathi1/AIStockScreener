from __future__ import annotations

import datetime as dt
import logging
import os
from zoneinfo import ZoneInfo

from .config import load_settings
from .logging_utils import configure_logging
from .news_client import NewsClient
from .nse_client import compute_moves, select_top_movers
from .reason_engine import generate_reason, generate_reason_with_summarization
from .telegram_client import TelegramClient
from .llm_reasoner import generate_reason_with_llm
from .scraper_reason_pipeline import generate_reason_with_scraper
from .telegram_reason_formatter import format_reason_style_message

logger = logging.getLogger(__name__)


def _today_in_ist() -> dt.date:
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = dt.datetime.now(ist)
    return now_ist.date()


def main() -> None:
    configure_logging()
    settings = load_settings()
    logger.info("Starting daily job")

    trade_date = _today_in_ist()
    # Skip weekends quickly – NSE cash market is closed.
    # For local testing, you can force a run by setting ALLOW_WEEKEND_RUN=true.
    allow_weekend = os.getenv("ALLOW_WEEKEND_RUN", "false").lower() == "true"
    if trade_date.weekday() >= 5 and not allow_weekend:
        logger.info("Weekend detected (%s), skipping run", trade_date.isoformat())
        return

    logger.info("Fetching NSE movers in %.1f%%-%.1f%% band", settings.min_move_percent, settings.max_move_percent)
    all_movers = compute_moves(
        min_abs_change=settings.min_move_percent,
        max_abs_change=settings.max_move_percent,
    )
    movers = select_top_movers(all_movers, max_per_side=settings.max_movers_per_side)
    logger.info("Computed %d raw movers, selected %d movers for processing", len(all_movers), len(movers))

    news_client = NewsClient(
        api_key=settings.news_api_key,
        base_url=settings.news_api_base_url,
    )

    reasons_by_symbol: dict[str, str] = {}

    use_summarization = os.getenv("ENABLE_SUMMARIZATION", "false").lower() == "true"
    use_llm = os.getenv("USE_LLM_REASONING", "false").lower() == "true"
    reason_provider = os.getenv("REASON_PROVIDER", "").strip().lower()
    if not reason_provider:
        if use_llm:
            reason_provider = "openai"
        elif use_summarization:
            reason_provider = "summarization"
        else:
            reason_provider = "legacy"
    logger.info("Reason provider selected: %s", reason_provider)

    for mover in movers:
        logger.info(
            "Processing %s (%s) %.2f%% %s",
            mover.symbol,
            mover.company_name,
            mover.percent_change,
            mover.direction,
        )
        if reason_provider == "scraper":
            reason = generate_reason_with_scraper(
                symbol=mover.symbol,
                company_name=mover.company_name,
                direction=mover.direction,
                percent_change=mover.percent_change,
            )
        else:
            articles = news_client.fetch_news(
                symbol=mover.symbol,
                company_name=mover.company_name,
            )

            if reason_provider == "openai":
                reason = generate_reason_with_llm(
                    symbol=mover.symbol,
                    company_name=mover.company_name,
                    direction=mover.direction,
                    percent_change=mover.percent_change,
                    articles=articles,
                )
            elif reason_provider == "summarization":
                reason = generate_reason_with_summarization(
                    symbol=mover.symbol,
                    company_name=mover.company_name,
                    direction=mover.direction,
                    percent_change=mover.percent_change,
                    articles=articles,
                )
            else:
                reason = generate_reason(
                    symbol=mover.symbol,
                    company_name=mover.company_name,
                    direction=mover.direction,
                    percent_change=mover.percent_change,
                    articles=articles,
            )
        reasons_by_symbol[mover.symbol] = reason
        logger.info("Reason generated for %s", mover.symbol)

    if movers:
        telegram = TelegramClient(settings)
        if reason_provider == "scraper":
            full_text = format_reason_style_message(
                trade_date=trade_date.isoformat(),
                movers=movers,
                reasons_by_symbol=reasons_by_symbol,
            )
            lines = full_text.split("\n")
            current = ""
            chunks: list[str] = []
            for line in lines:
                candidate = f"{current}\n{line}" if current else line
                if len(candidate) > 3500:
                    chunks.append(current)
                    current = line
                else:
                    current = candidate
            if current:
                chunks.append(current)
            logger.info("Sending %d Telegram chunk(s) in scraper format", len(chunks))
            for chunk in chunks:
                telegram.send_text(chunk)
        else:
            logger.info("Sending Telegram summary in legacy/openai format")
            telegram.send_movers_summary(
                trade_date=trade_date.isoformat(),
                movers=movers,
                reasons_by_symbol=reasons_by_symbol,
            )
    else:
        logger.info("No movers found, nothing to send")

    logger.info("Daily job finished")


if __name__ == "__main__":
    main()
