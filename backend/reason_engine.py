from __future__ import annotations

import os
from typing import Iterable, List, Optional

from .news_client import NewsArticle


def _contains(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def generate_reason(
    symbol: str,
    company_name: str,
    direction: str,
    percent_change: float,
    articles: Iterable[NewsArticle],
) -> str:
    """
    Generate a short, human-readable reason string for a stock move based on
    recent headlines. This is intentionally simple and cheap (no heavy models).
    """
    article_list: List[NewsArticle] = list(articles)

    if not article_list:
        return (
            f"{symbol} moved {percent_change:.1f}% {direction}, but no clear news "
            f"could be found in the last couple of days."
        )

    combined = " ".join(
        f"{a.title} {a.description or ''}" for a in article_list
    ).lower()

    # Try to pick the most specific explanations first.

    # Mergers, acquisitions, stake changes, corporate actions.
    if _contains(
        combined,
        "merger",
        "acquisition",
        "amalgamation",
        "stake sale",
        "stake-sale",
        "stake buy",
        "buyback",
        "divestment",
        "disinvestment",
        "open offer",
        "deal with",
    ):
        top = article_list[0]
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, seemingly on "
            f"news of a merger / acquisition or other corporate action. "
            f"Example headline: \"{top.title}\""
        )

    # Earnings / results.
    if _contains(combined, "earnings", "q1", "q2", "q3", "q4", "results", "profit"):
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, likely driven "
            f"by recent earnings or results updates."
        )

    # Broker / rating actions.
    if _contains(combined, "upgrade", "downgrade", "rating", "target price", "initiate"):
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, possibly "
            f"due to brokerage rating or target price changes."
        )

    # Orders / contracts / MoUs.
    if _contains(combined, "deal", "order", "contract", "tender", "mou", "agreement"):
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, seemingly on "
            f"news of new orders, contracts, tenders or MoUs."
        )

    # Regulatory / compliance.
    if _contains(combined, "regulator", "sebi", "penalty", "investigation", "probe"):
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, likely related "
            f"to regulatory or compliance news."
        )

    # Fallback: surface the top headline explicitly so the user can see context.
    top = article_list[0]
    return (
        f"{company_name} moved {percent_change:.1f}% {direction}. "
        f"Top related headline: \"{top.title}\""
    )


_SUMMARIZER = None


def _get_summarizer():
    """
    Lazily construct a summarization pipeline if transformers is available.

    This keeps the dependency optional: if transformers or its models are not
    installed, we simply fall back to the heuristic generator.
    """
    global _SUMMARIZER
    if _SUMMARIZER is not None:
        return _SUMMARIZER

    try:
        from transformers import pipeline  # type: ignore
    except Exception:
        return None

    model_name = os.getenv("SUMMARIZATION_MODEL", "sshleifer/distilbart-cnn-12-6")
    try:
        _SUMMARIZER = pipeline("summarization", model=model_name)
    except Exception:
        _SUMMARIZER = None
    return _SUMMARIZER


def generate_reason_with_summarization(
    symbol: str,
    company_name: str,
    direction: str,
    percent_change: float,
    articles: Iterable[NewsArticle],
) -> str:
    """
    Optional AI-enhanced reason using a local summarization model.

    If a summarizer is not available, degrades gracefully to the heuristic
    implementation.
    """
    summarizer = _get_summarizer()
    article_list: List[NewsArticle] = list(articles)

    if not summarizer or not article_list:
        return generate_reason(
            symbol=symbol,
            company_name=company_name,
            direction=direction,
            percent_change=percent_change,
            articles=article_list,
        )

    body_parts: List[str] = []
    for a in article_list[:5]:
        part = a.title
        if a.description:
            part += f". {a.description}"
        body_parts.append(part)

    base = (
        f"Stock {symbol} ({company_name}) moved {percent_change:.1f}% {direction}. "
        f"Recent news: "
    )
    text = base + " ".join(body_parts)

    try:
        summary_outputs = summarizer(
            text,
            max_length=int(os.getenv("SUMMARY_MAX_LENGTH", "80")),
            min_length=int(os.getenv("SUMMARY_MIN_LENGTH", "25")),
            do_sample=False,
        )
        summary_text = ""
        if isinstance(summary_outputs, list) and summary_outputs:
            summary_text = summary_outputs[0].get("summary_text", "")
    except Exception:
        summary_text = ""

    if not summary_text:
        return generate_reason(
            symbol=symbol,
            company_name=company_name,
            direction=direction,
            percent_change=percent_change,
            articles=article_list,
        )

    return summary_text

