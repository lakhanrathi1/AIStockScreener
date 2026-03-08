from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
_FEED_HEALTH_CACHE: dict[str, bool] = {}


@dataclass
class ScrapedHeadline:
    headline: str
    url: str
    publication: str
    timestamp: dt.datetime | None
    summary: str | None = None


@dataclass
class NewsSource:
    name: str
    landing_url: str
    domain: str
    rss_url: str | None = None


INDIAN_MARKET_SOURCES: list[NewsSource] = [
    NewsSource(
        name="Moneycontrol",
        landing_url="https://www.moneycontrol.com/news/business/stocks/",
        domain="moneycontrol.com",
    ),
    NewsSource(
        name="Economic Times Markets",
        landing_url="https://economictimes.indiatimes.com/markets",
        domain="economictimes.indiatimes.com",
    ),
    NewsSource(
        name="Business Standard Markets",
        landing_url="https://www.business-standard.com/markets",
        domain="business-standard.com",
    ),
    NewsSource(
        name="Business Standard",
        landing_url="https://www.business-standard.com/",
        domain="business-standard.com",
    ),
    NewsSource(
        name="Mint Markets",
        landing_url="https://www.livemint.com/market",
        domain="livemint.com",
    ),
    NewsSource(
        name="Reuters Business",
        landing_url="https://www.reuters.com/markets",
        domain="reuters.com",
        rss_url="https://feeds.reuters.com/reuters/businessNews",
    ),
    NewsSource(
        name="CNBC TV18 Markets",
        landing_url="https://www.cnbctv18.com/market/",
        domain="cnbctv18.com",
    ),
    NewsSource(
        name="Financial Express Markets",
        landing_url="https://www.financialexpress.com/market/",
        domain="financialexpress.com",
    ),
    NewsSource(
        name="Bloomberg Markets",
        landing_url="https://www.bloomberg.com/markets",
        domain="bloomberg.com",
    ),
    NewsSource(
        name="Zee Business Markets",
        landing_url="https://www.zeebiz.com/markets",
        domain="zeebiz.com",
    ),
]

GOOGLE_NEWS_NAME = "Google News"


def _safe_get(url: str, timeout: int = 10) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException:
        return ""
    return resp.text


def _google_news_feed(query: str) -> str:
    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    )


def _is_feed_reachable(feed_url: str, timeout: int = 10) -> bool:
    cached = _FEED_HEALTH_CACHE.get(feed_url)
    if cached is not None:
        return cached

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(feed_url, headers=headers, timeout=timeout, allow_redirects=True)
        ok = resp.status_code == 200
        if not ok:
            logger.warning("Skipping feed %s due to HTTP %s", feed_url, resp.status_code)
    except requests.RequestException as exc:
        ok = False
        logger.warning("Skipping feed %s due to connection error: %s", feed_url, exc)

    _FEED_HEALTH_CACHE[feed_url] = ok
    return ok


def _parse_feed(feed_url: str, publication: str, limit: int) -> list[ScrapedHeadline]:
    if not _is_feed_reachable(feed_url):
        return []

    parsed = feedparser.parse(feed_url)
    out: list[ScrapedHeadline] = []
    for entry in parsed.entries[:limit]:
        headline = getattr(entry, "title", "") or ""
        url = getattr(entry, "link", "") or ""
        if not headline or not url:
            continue
        published_at = None
        stamp = getattr(entry, "published_parsed", None) or getattr(
            entry, "updated_parsed", None
        )
        if stamp:
            try:
                published_at = dt.datetime(
                    year=stamp.tm_year,
                    month=stamp.tm_mon,
                    day=stamp.tm_mday,
                    hour=stamp.tm_hour,
                    minute=stamp.tm_min,
                    second=stamp.tm_sec,
                    tzinfo=dt.timezone.utc,
                )
            except Exception:
                published_at = None
        summary = getattr(entry, "summary", None)
        out.append(
            ScrapedHeadline(
                headline=headline.strip(),
                url=url.strip(),
                publication=publication,
                timestamp=published_at,
                summary=(summary or "").strip() or None,
            )
        )
    return out


def _scrape_listing_page(
    source: NewsSource,
    query_tokens: list[str],
    limit: int,
) -> list[ScrapedHeadline]:
    html = _safe_get(source.landing_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    out: list[ScrapedHeadline] = []
    seen: set[str] = set()
    lowered_tokens = [t.lower() for t in query_tokens if t]

    for a in soup.find_all("a", href=True):
        headline = a.get_text(" ", strip=True)
        if len(headline) < 20:
            continue

        low_headline = headline.lower()
        if lowered_tokens and not any(token in low_headline for token in lowered_tokens):
            continue

        href = a["href"].strip()
        if href.startswith("#"):
            continue
        full_url = href if href.startswith("http") else urljoin(source.landing_url, href)

        host = urlparse(full_url).netloc.lower()
        if source.domain not in host:
            continue

        key = f"{headline.lower()}|{full_url}"
        if key in seen:
            continue
        seen.add(key)

        out.append(
            ScrapedHeadline(
                headline=headline,
                url=full_url,
                publication=source.name,
                timestamp=None,
                summary=None,
            )
        )
        if len(out) >= limit:
            break
    return out


def _dedup_headlines(items: Iterable[ScrapedHeadline], limit: int) -> list[ScrapedHeadline]:
    seen: set[str] = set()
    out: list[ScrapedHeadline] = []
    for item in items:
        key = f"{item.headline.strip().lower()}|{item.url.strip().split('?')[0]}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def fetch_multi_source_headlines(
    symbol: str,
    company_name: Optional[str] = None,
    max_per_source: int = 4,
    max_total: int = 50,
) -> List[ScrapedHeadline]:
    logger.info("Scraper fetch started for %s (%s)", symbol, company_name or symbol)
    cleaned_symbol = (symbol or "").strip()
    cleaned_name = (company_name or "").strip()

    query_tokens = [cleaned_symbol]
    if cleaned_name and cleaned_name.lower() != cleaned_symbol.lower():
        query_tokens.append(cleaned_name)
    query_tokens.append("stock")

    query_variants: list[str] = []
    query_seen: set[str] = set()

    def _add_query(q: str) -> None:
        q = " ".join(q.split()).strip()
        if not q:
            return
        low = q.lower()
        if low not in query_seen:
            query_seen.add(low)
            query_variants.append(q)

    _add_query(cleaned_symbol)
    _add_query(f"{cleaned_symbol} stock")
    if cleaned_name and cleaned_name.lower() != cleaned_symbol.lower():
        _add_query(cleaned_name)
        _add_query(f"{cleaned_name} stock")
        _add_query(f"{cleaned_symbol} {cleaned_name} stock")

    all_items: list[ScrapedHeadline] = []

    for source in INDIAN_MARKET_SOURCES:
        before = len(all_items)
        for q in query_variants:
            google_query = f"{q} site:{source.domain}"
            all_items.extend(
                _parse_feed(
                    feed_url=_google_news_feed(google_query),
                    publication=source.name,
                    limit=max_per_source,
                )
            )

        if source.rss_url:
            all_items.extend(
                _parse_feed(
                    feed_url=source.rss_url,
                    publication=source.name,
                    limit=max_per_source,
                )
            )

        all_items.extend(
            _scrape_listing_page(
                source=source,
                query_tokens=query_tokens,
                limit=max_per_source,
            )
        )
        logger.info(
            "Source %s produced %d item(s)",
            source.name,
            len(all_items) - before,
        )

    all_items.extend(
        _parse_feed(
            feed_url=_google_news_feed(
                f"{cleaned_symbol} {cleaned_name} NSE stock news"
            ),
            publication=GOOGLE_NEWS_NAME,
            limit=max_per_source * 4,
        )
    )

    deduped = _dedup_headlines(all_items, limit=max_total)
    logger.info(
        "Scraper fetched %d raw headline(s), %d after dedup",
        len(all_items),
        len(deduped),
    )
    return deduped
