from __future__ import annotations

import logging
import os
from textwrap import shorten
from typing import Iterable, List

from .news_client import NewsArticle
from .reason_engine import generate_reason

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _build_prompt(
    symbol: str,
    company_name: str,
    direction: str,
    percent_change: float,
    articles: Iterable[NewsArticle],
) -> str:
    """
    Build a concise prompt for an LLM to explain the stock move based on news.
    """
    lines: List[str] = []
    lines.append(
        "You are a financial analyst specialising in the Indian stock market."
    )
    lines.append(
        "Given a stock's price move and recent news headlines, explain the most likely"
        " reason for the move in clear, simple English."
    )
    lines.append("")
    lines.append(f"Stock: {symbol} ({company_name})")
    lines.append(f"Move: {percent_change:.2f}% {direction}")
    lines.append("")
    lines.append("Recent news (most recent first):")

    for idx, a in enumerate(articles):
        title = a.title or ""
        desc = a.description or ""
        when = a.published_at.isoformat() if a.published_at else ""
        snippet = shorten(f"{title}. {desc}", width=260, placeholder="…")
        lines.append(f"{idx+1}. [{when}] {snippet}")

    lines.append("")
    lines.append(
        "Task: In 3–6 short sentences, explain the most likely reason for why this "
        "stock moved today. Focus on concrete news (mergers, orders, earnings, "
        "regulation, broker calls, etc.). If you are not sure, say that clearly."
    )

    return "\n".join(lines)


def generate_reason_with_llm(
    symbol: str,
    company_name: str,
    direction: str,
    percent_change: float,
    articles: Iterable[NewsArticle],
) -> str:
    """
    Use an LLM (OpenAI API) to generate a richer natural language explanation.

    Falls back to a generic sentence if the client or key is not configured.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    logger.info("LLM reasoning requested for %s with model=%s", symbol, model)

    if OpenAI is None or not api_key:
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, but the AI "
            f"reason service is not configured (no OPENAI_API_KEY)."
        )

    article_list = list(articles)
    if not article_list:
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, but no clear "
            f"news could be found in the last couple of days."
        )

    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(symbol, company_name, direction, percent_change, article_list)
    temperature = _env_float("OPENAI_TEMPERATURE", 0.2)
    max_tokens = _env_int("OPENAI_MAX_TOKENS", 256)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise, detail-oriented Indian equity analyst.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = completion.choices[0].message.content or ""
        logger.info("LLM reason generated for %s", symbol)
        return text.strip()
    except Exception as exc:
        # If OpenAI quota/rate limits are hit, degrade to the heuristic explainer.
        if "insufficient_quota" in str(exc).lower() or "ratelimit" in type(exc).__name__.lower():
            logger.warning("LLM quota/rate limit for %s; falling back to heuristic reason", symbol)
            return generate_reason(
                symbol=symbol,
                company_name=company_name,
                direction=direction,
                percent_change=percent_change,
                articles=article_list,
            )
        err_type = type(exc).__name__
        err_msg = str(exc).strip().replace("\n", " ")
        err_msg = shorten(err_msg, width=140, placeholder="…")
        logger.warning("LLM call failed for %s: %s", symbol, err_type)
        return (
            f"{company_name} moved {percent_change:.1f}% {direction}, but there was "
            f"an error calling the external AI service "
            f"({err_type}: {err_msg})."
        )
