"""Optional keyed news/search providers. Each receives ONLY the query string.

They are `available()` only when the corresponding key is set in the environment. RSS remains
the default and always works.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from dateutil import parser as dateparser

from ...config import get_settings
from ..base import NewsProvider, ProviderError, RawArticle


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = dateparser.parse(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


class BraveNewsProvider(NewsProvider):
    name = "brave"
    requires_key = True

    def available(self) -> bool:
        return bool(get_settings().brave_api_key)

    def fetch(self, feed_url=None, query=None, *, limit=20, feed_id=None) -> list[RawArticle]:
        if not query:
            return []
        try:
            r = httpx.get(
                "https://api.search.brave.com/res/v1/news/search",
                params={"q": query, "count": min(limit, 50), "freshness": "pw"},
                headers={"X-Subscription-Token": get_settings().brave_api_key, "Accept": "application/json"},
                timeout=20,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(f"Brave search failed: {e}", provider=self.name) from e
        out = []
        for it in r.json().get("results", []):
            out.append(RawArticle(url=it["url"], title=it.get("title", ""), publication=(it.get("meta_url") or {}).get("hostname", ""), published_at=_dt(it.get("page_age")), summary=it.get("description", ""), provider=self.name, feed_id=feed_id))
        return out


class TavilyNewsProvider(NewsProvider):
    name = "tavily"
    requires_key = True

    def available(self) -> bool:
        return bool(get_settings().tavily_api_key)

    def fetch(self, feed_url=None, query=None, *, limit=20, feed_id=None) -> list[RawArticle]:
        if not query:
            return []
        try:
            r = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": get_settings().tavily_api_key, "query": query, "topic": "news", "max_results": min(limit, 20), "days": 7},
                timeout=30,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(f"Tavily search failed: {e}", provider=self.name) from e
        return [
            RawArticle(url=it["url"], title=it.get("title", ""), summary=it.get("content", "")[:2000], published_at=_dt(it.get("published_date")), provider=self.name, feed_id=feed_id)
            for it in r.json().get("results", [])
        ]


class NewsAPIProvider(NewsProvider):
    name = "newsapi"
    requires_key = True

    def available(self) -> bool:
        return bool(get_settings().newsapi_key)

    def fetch(self, feed_url=None, query=None, *, limit=30, feed_id=None) -> list[RawArticle]:
        if not query:
            return []
        try:
            r = httpx.get(
                "https://newsapi.org/v2/everything",
                params={"q": query, "pageSize": min(limit, 100), "sortBy": "publishedAt", "language": "en"},
                headers={"X-Api-Key": get_settings().newsapi_key},
                timeout=20,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(f"NewsAPI failed: {e}", provider=self.name) from e
        out = []
        for it in r.json().get("articles", []):
            out.append(RawArticle(url=it["url"], title=it.get("title") or "", publication=(it.get("source") or {}).get("name", ""), author=it.get("author"), published_at=_dt(it.get("publishedAt")), summary=it.get("description") or "", content=it.get("content") or "", provider=self.name, feed_id=feed_id))
        return out


def get_news_provider(name: str) -> NewsProvider:
    from .rss import GoogleNewsRSSProvider, RSSProvider

    table = {
        "rss": RSSProvider,
        "google_news_rss": GoogleNewsRSSProvider,
        "brave": BraveNewsProvider,
        "tavily": TavilyNewsProvider,
        "newsapi": NewsAPIProvider,
    }
    cls = table.get(name)
    if cls is None:
        raise ProviderError(f"unknown news provider {name}", retryable=False)
    return cls()


def provider_status() -> list[dict]:
    from .rss import GoogleNewsRSSProvider, RSSProvider

    out = []
    for p in (RSSProvider(), GoogleNewsRSSProvider(), BraveNewsProvider(), TavilyNewsProvider(), NewsAPIProvider()):
        out.append({"name": p.name, "requires_key": p.requires_key, "available": p.available()})
    return out
