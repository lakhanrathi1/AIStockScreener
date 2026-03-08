from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import List, Optional

import feedparser
import requests

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    title: str
    url: str
    source: str | None
    published_at: dt.datetime | None
    description: str | None = None


class NewsClient:
    """
    Simple news client for fetching stock-related news.

    By default, it targets the MarketAux-style API, but the implementation is
    intentionally small and can be adapted later if you switch providers.
    """

    def __init__(self, api_key: str | None, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def fetch_news(
        self,
        symbol: str,
        company_name: Optional[str] = None,
        max_articles: int = 5,
        lookback_hours: int = 48,
    ) -> List[NewsArticle]:
        logger.info("Fetching news for %s (%s)", symbol, company_name or symbol)
        # Try primary JSON news API first (if configured).
        articles: List[NewsArticle] = []
        if self.api_key:
            articles = self._fetch_from_primary_api(
                symbol=symbol,
                company_name=company_name,
                max_articles=max_articles,
                lookback_hours=lookback_hours,
            )
        # Fallback to Google News RSS if there is no API key or no data.
        if not articles:
            logger.info("Primary API returned no articles; using Google News RSS fallback")
            articles = self._fetch_from_google_news_rss(
                symbol=symbol,
                company_name=company_name,
                max_articles=max_articles,
            )
        logger.info("Fetched %d news article(s) for %s", len(articles), symbol)
        return articles

    def _fetch_from_primary_api(
        self,
        symbol: str,
        company_name: Optional[str],
        max_articles: int,
        lookback_hours: int,
    ) -> List[NewsArticle]:
        if not self.api_key:
            return []

        params = {
            "api_token": self.api_key,
            "limit": max_articles,
            "language": "en",
            "countries": "in",
        }

        query_parts = [symbol]
        if company_name:
            query_parts.append(company_name)
        query = " ".join(query_parts)
        params["search"] = query

        now = dt.datetime.utcnow()
        since = now - dt.timedelta(hours=lookback_hours)
        params["published_after"] = since.isoformat(timespec="seconds") + "Z"

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Primary news API request failed for %s", symbol)
            return []

        data = response.json()
        articles_raw = data.get("data") or data.get("articles") or []

        return self._parse_articles_from_json(articles_raw)

    @staticmethod
    def _parse_articles_from_json(items: list) -> List[NewsArticle]:
        articles: List[NewsArticle] = []
        for item in items:
            title = item.get("title") or ""
            url = item.get("url") or item.get("link") or ""
            if not title or not url:
                continue

            source = None
            source_obj = item.get("source")
            if isinstance(source_obj, dict):
                source = source_obj.get("name")
            elif isinstance(source_obj, str):
                source = source_obj

            published_at = None
            published_str = item.get("published_at") or item.get("publishedAt")
            if isinstance(published_str, str):
                try:
                    published_at = dt.datetime.fromisoformat(
                        published_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = None

            description = item.get("description")

            articles.append(
                NewsArticle(
                    title=title,
                    url=url,
                    source=source,
                    published_at=published_at,
                    description=description,
                )
            )
        return articles

    @staticmethod
    def _fetch_from_google_news_rss(
        symbol: str,
        company_name: Optional[str],
        max_articles: int,
    ) -> List[NewsArticle]:
        # Google News RSS – public, no key needed.
        query_parts = [symbol]
        if company_name:
            query_parts.append(company_name)
        query = "+".join(part.replace(" ", "+") for part in query_parts + ["NSE"])
        rss_url = (
            "https://news.google.com/rss/search?"
            f"q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        )

        feed = feedparser.parse(rss_url)
        articles: List[NewsArticle] = []

        for entry in feed.entries[:max_articles]:
            title = getattr(entry, "title", "")
            link = getattr(entry, "link", "")
            if not title or not link:
                continue

            source = None
            source_obj = getattr(entry, "source", None)
            if source_obj is not None:
                source = getattr(source_obj, "title", None)

            published_at = None
            published_parsed = getattr(entry, "published_parsed", None) or getattr(
                entry, "updated_parsed", None
            )
            if published_parsed:
                try:
                    published_at = dt.datetime(
                        year=published_parsed.tm_year,
                        month=published_parsed.tm_mon,
                        day=published_parsed.tm_mday,
                        hour=published_parsed.tm_hour,
                        minute=published_parsed.tm_min,
                        second=published_parsed.tm_sec,
                        tzinfo=dt.timezone.utc,
                    )
                except Exception:
                    published_at = None

            summary = getattr(entry, "summary", None)

            articles.append(
                NewsArticle(
                    title=title,
                    url=link,
                    source=source,
                    published_at=published_at,
                    description=summary,
                )
            )

        return articles
