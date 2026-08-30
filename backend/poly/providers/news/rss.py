"""RSS / Atom provider (works with no API keys). Also powers Google News RSS queries."""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from urllib.parse import quote_plus

import feedparser
import httpx
from dateutil import parser as dateparser

from ..base import NewsProvider, ProviderError, RawArticle

log = logging.getLogger(__name__)
USER_AGENT = "Poly/0.1 (+local news intelligence; RSS reader)"


def _parse_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime.fromtimestamp(time.mktime(val), tz=UTC)
            except (OverflowError, ValueError):
                pass
    for key in ("published", "updated", "dc_date"):
        val = entry.get(key)
        if val:
            try:
                d = dateparser.parse(val)
                return d if d.tzinfo else d.replace(tzinfo=UTC)
            except (ValueError, OverflowError, TypeError):
                pass
    return None


def _strip_html(text: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(text.split())


def parse_feed_bytes(data: bytes | str, *, feed_id: str | None = None, provider: str = "rss", limit: int = 50) -> list[RawArticle]:
    parsed = feedparser.parse(data)
    publication = (parsed.feed.get("title") or "").strip()
    out: list[RawArticle] = []
    for e in parsed.entries[:limit]:
        link = (e.get("link") or "").strip()
        title = _strip_html(e.get("title") or "").strip()
        if not link or not title:
            continue
        summary = _strip_html(e.get("summary") or e.get("description") or "")
        content = ""
        if e.get("content"):
            content = _strip_html(" ".join(c.get("value", "") for c in e["content"]))
        author = e.get("author") or (e.get("authors") or [{}])[0].get("name")
        source = (e.get("source") or {}).get("title")
        out.append(
            RawArticle(
                url=link,
                title=title,
                publication=source or publication,
                author=author,
                published_at=_parse_date(e),
                summary=summary[:2000],
                content=content,
                provider=provider,
                feed_id=feed_id,
                raw={"id": e.get("id"), "tags": [t.get("term") for t in e.get("tags", [])]},
            )
        )
    return out


class RSSProvider(NewsProvider):
    name = "rss"
    requires_key = False

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def available(self) -> bool:
        return True

    def fetch(self, feed_url: str | None = None, query: str | None = None, *, limit: int = 50, feed_id: str | None = None) -> list[RawArticle]:
        if not feed_url and query:
            feed_url = google_news_url(query)
        if not feed_url:
            return []
        if feed_url.startswith("file://"):  # local fixture / offline development
            from pathlib import Path

            p = Path(feed_url[len("file://"):])
            if not p.exists():
                raise ProviderError(f"feed file not found: {p}", provider=self.name, retryable=False)
            return parse_feed_bytes(p.read_bytes(), feed_id=feed_id, provider=self.name, limit=limit)
        try:
            r = httpx.get(feed_url, timeout=self.timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(f"RSS fetch failed for {feed_url}: {e}", provider=self.name) from e
        return parse_feed_bytes(r.content, feed_id=feed_id, provider=self.name, limit=limit)


def google_news_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"


class GoogleNewsRSSProvider(RSSProvider):
    name = "google_news_rss"

    def fetch(self, feed_url=None, query=None, *, limit=50, feed_id=None):
        return super().fetch(feed_url or (google_news_url(query) if query else None), None, limit=limit, feed_id=feed_id)
