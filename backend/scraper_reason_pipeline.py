from __future__ import annotations

import logging

from .article_extractor import extract_article
from .multi_source_news import fetch_multi_source_headlines
from .reason_phrase_engine import build_reason_text, rank_reason_candidate

logger = logging.getLogger(__name__)


def generate_reason_with_scraper(
    symbol: str,
    company_name: str,
    direction: str,
    percent_change: float,
    max_headlines: int = 40,
) -> str:
    logger.info("Running scraper reason pipeline for %s", symbol)
    headlines = fetch_multi_source_headlines(
        symbol=symbol,
        company_name=company_name,
        max_per_source=4,
        max_total=max_headlines,
    )
    logger.info("Received %d scraped headline(s) for %s", len(headlines), symbol)
    if not headlines:
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, but no matching "
            "news was found across configured sources."
        )

    candidates = []
    for item in headlines[:20]:
        extracted = extract_article(item.url)
        candidate = rank_reason_candidate(
            symbol=symbol,
            company_name=company_name,
            headline=item,
            extracted=extracted,
        )
        if candidate:
            candidates.append(candidate)
    logger.info("Built %d reason candidate(s) for %s", len(candidates), symbol)

    return build_reason_text(
        company_name=company_name,
        direction=direction,
        percent_change=percent_change,
        candidates=candidates,
    )
