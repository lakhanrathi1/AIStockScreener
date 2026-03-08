from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from .article_extractor import ExtractedArticle
from .multi_source_news import ScrapedHeadline


@dataclass
class ReasonCandidate:
    publication: str
    headline: str
    url: str
    reason_phrase: str
    score: int


_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bafter\s+([^,.:\n]{8,160})", re.IGNORECASE),
    re.compile(r"\bamid\s+([^,.:\n]{8,160})", re.IGNORECASE),
    re.compile(r"\bon\s+([^,.:\n]{8,160})", re.IGNORECASE),
    re.compile(r"\bdue to\s+([^,.:\n]{8,160})", re.IGNORECASE),
    re.compile(r"\bbecause of\s+([^,.:\n]{8,160})", re.IGNORECASE),
    re.compile(r"\bfollowing\s+([^,.:\n]{8,160})", re.IGNORECASE),
    re.compile(r"\bafter announcing\s+([^,.:\n]{8,160})", re.IGNORECASE),
    re.compile(r"\bafter securing\s+([^,.:\n]{8,160})", re.IGNORECASE),
    re.compile(r"\bon winning\s+([^,.:\n]{8,160})", re.IGNORECASE),
]


def _clean_reason(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned.strip(" -:;,.")


def extract_reason_phrase(text: str) -> str | None:
    for pattern in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        phrase = _clean_reason(match.group(1))
        if len(phrase) >= 8:
            return phrase
    return None


def rank_reason_candidate(
    symbol: str,
    company_name: str,
    headline: ScrapedHeadline,
    extracted: ExtractedArticle,
) -> Optional[ReasonCandidate]:
    search_text = " ".join(
        [
            headline.headline,
            headline.summary or "",
            extracted.title,
            extracted.text[:1200],
        ]
    )
    phrase = extract_reason_phrase(search_text)
    if not phrase and (extracted.error or not extracted.text.strip()):
        fallback_text = " ".join([headline.headline, headline.summary or ""])
        phrase = extract_reason_phrase(fallback_text)
    if not phrase:
        return None

    lowered = search_text.lower()
    score = 0
    if symbol.lower() in lowered:
        score += 2
    if company_name and company_name.lower() in lowered:
        score += 2
    if len(extracted.text) > 500:
        score += 1

    return ReasonCandidate(
        publication=headline.publication,
        headline=headline.headline,
        url=headline.url,
        reason_phrase=phrase,
        score=score,
    )


def build_reason_text(
    company_name: str,
    direction: str,
    percent_change: float,
    candidates: Iterable[ReasonCandidate],
) -> str:
    sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
    if not sorted_candidates:
        trend_word = "rose" if direction == "up" else "fell"
        return (
            f"{company_name} {trend_word} {abs(percent_change):.1f}% with no clearly "
            "extractable trigger phrase from current news."
        )

    top = sorted_candidates[0]
    trend_word = "surged" if direction == "up" else "declined"
    return (
        f"{company_name} {trend_word} {abs(percent_change):.1f}% after {top.reason_phrase}. "
        f"(Source: {top.publication})"
    )
