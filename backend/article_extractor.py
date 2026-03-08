from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import List, Optional

try:
    from newspaper import Article  # type: ignore
except Exception:  # pragma: no cover
    Article = None  # type: ignore

logger = logging.getLogger(__name__)
_missing_newspaper_warned = False


@dataclass
class ExtractedArticle:
    title: str
    text: str
    authors: List[str]
    publish_date: dt.datetime | None
    error: str | None = None


def extract_article(url: str, language: str = "en") -> ExtractedArticle:
    global _missing_newspaper_warned

    if not Article:
        if not _missing_newspaper_warned:
            logger.warning(
                "newspaper3k unavailable; article extraction disabled. "
                "Install dependencies in the active venv to enable it."
            )
            _missing_newspaper_warned = True
        return ExtractedArticle(
            title="",
            text="",
            authors=[],
            publish_date=None,
            error="newspaper3k is not installed",
        )

    try:
        article = Article(url=url, language=language)
        article.download()
        article.parse()
    except Exception as exc:
        logger.warning("Article extraction failed for %s: %s", url, exc)
        return ExtractedArticle(
            title="",
            text="",
            authors=[],
            publish_date=None,
            error=str(exc),
        )

    publish_date: Optional[dt.datetime] = article.publish_date
    logger.debug("Extracted article text (%d chars) from %s", len(article.text or ""), url)
    return ExtractedArticle(
        title=(article.title or "").strip(),
        text=(article.text or "").strip(),
        authors=list(article.authors or []),
        publish_date=publish_date,
        error=None,
    )
