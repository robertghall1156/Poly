"""News ingestion: fetch → normalise → dedupe → cluster → analyse → save.

`run_ingest(db)` is what the daily job and the "Run ingest now" button call.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Article, Feed, Source, Story, StoryEvent
from ..providers.base import ProviderError, RawArticle
from ..providers.news.apis import get_news_provider
from ..providers.news.default_feeds import DEFAULT_FEEDS
from . import settings as settings_service
from .privacy import NetworkPolicy
from .topics import tag_topics

log = logging.getLogger(__name__)

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "cmpid", "ncid", "ocid", "smid", "smtyp", "partner", "_ga"}
_WS = re.compile(r"\s+")
_TITLE_NOISE = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,40}$")  # " - The New York Times"


def canonicalize_url(url: str) -> str:
    url = url.strip()
    parts = urlsplit(url)
    scheme = "https" if parts.scheme in ("http", "https") else parts.scheme
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")]
    path = re.sub(r"/+$", "", parts.path) or "/"
    if path.endswith("/amp"):
        path = path[:-4]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(query)), ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    t = _WS.sub(" ", title or "").strip()
    t = _TITLE_NOISE.sub("", t)
    return t.strip()


def _title_tokens(title: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", normalize_title(title).lower()) if len(w) > 2]


def title_simhash(title: str) -> str:
    """64-bit simhash over title word shingles. Near-identical titles differ in few bits."""
    tokens = _title_tokens(title)
    feats = tokens + [a + " " + b for a, b in zip(tokens, tokens[1:])]
    if not feats:
        return "0" * 16
    v = [0] * 64
    for f in feats:
        h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= 1 << i
    return f"{out:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def content_hash(text: str) -> str:
    norm = _WS.sub(" ", (text or "").lower()).strip()
    return hashlib.sha256(norm[:5000].encode("utf-8")).hexdigest() if norm else ""


def _domain(url: str) -> str:
    n = urlsplit(url).netloc.lower()
    return n[4:] if n.startswith("www.") else n


def normalize(raw: RawArticle) -> dict[str, Any]:
    """Turn a provider result into Article column values."""
    url = raw.url.strip()
    canonical = canonicalize_url(url)
    title = normalize_title(raw.title)
    summary = _WS.sub(" ", raw.summary or "").strip()
    content = (raw.content or "").strip()
    published = raw.published_at
    if published and published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return {
        "url": url,
        "canonical_url": canonical,
        "url_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "title": title[:600],
        "title_simhash": title_simhash(title),
        "author": (raw.author or None),
        "publication": (raw.publication or _domain(url))[:200],
        "published_at": published,
        "summary": summary[:2000],
        "content": content,
        "content_hash": content_hash(content or summary),
        "topics": tag_topics(f"{title} {summary} {content[:2000]}"),
        "raw": raw.raw or {},
        "feed_id": raw.feed_id,
    }


def find_duplicate(db: Session, norm: dict[str, Any], *, recent: list[Article] | None = None, title_bits: int = 3) -> Article | None:
    """Exact URL, exact content, or near-identical title (simhash) within the recent window."""
    row = db.execute(select(Article).where(Article.url_hash == norm["url_hash"])).scalar_one_or_none()
    if row is not None:
        return row
    if norm["content_hash"]:
        row = db.execute(select(Article).where(Article.content_hash == norm["content_hash"]).limit(1)).scalar_one_or_none()
        if row is not None:
            return row
    pool = recent if recent is not None else db.execute(select(Article).where(Article.fetched_at > datetime.now(timezone.utc) - timedelta(days=7))).scalars().all()
    for a in pool:
        if a.title_simhash and hamming(a.title_simhash, norm["title_simhash"]) <= title_bits and normalize_title(a.title).lower()[:20] == norm["title"].lower()[:20]:
            return a
    return None


def ensure_default_feeds(db: Session) -> int:
    existing = {f.url for f in db.execute(select(Feed)).scalars()}
    added = 0
    for f in DEFAULT_FEEDS:
        if f["url"] in existing:
            continue
        source_id = None
        if f.get("source"):
            name, domain, stype, ideology, notes = f["source"]
            src = db.execute(select(Source).where(Source.domain == domain)).scalar_one_or_none()
            if src is None:
                src = Source(name=name, domain=domain, source_type=stype, ideology=ideology, reliability_notes=notes, is_primary=(stype == "government"))
                db.add(src)
                db.flush()
            source_id = src.id
        db.add(Feed(name=f["name"], url=f["url"], provider="rss", category=f.get("category", "general"), source_id=source_id))
        added += 1
    db.commit()
    return added


def _source_for(db: Session, url: str, publication: str) -> Source | None:
    dom = _domain(url)
    if dom.endswith("news.google.com"):
        return None
    src = db.execute(select(Source).where(Source.domain == dom)).scalar_one_or_none()
    if src is None and dom:
        stype = "government" if dom.endswith(".gov") else "other"
        src = Source(name=publication or dom, domain=dom, source_type=stype, is_primary=(stype == "government"))
        db.add(src)
        db.flush()
    return src


def fetch_feed(db: Session, feed: Feed, *, limit: int) -> list[RawArticle]:
    provider = get_news_provider(feed.provider)
    if not provider.available():
        raise ProviderError(f"provider {feed.provider} unavailable (missing key?)", provider=feed.provider, retryable=False)
    return provider.fetch(feed.url if feed.provider in ("rss", "google_news_rss") else None, feed.query, limit=limit, feed_id=feed.id)  # type: ignore[call-arg]


def ingest_raw_articles(db: Session, raws: list[RawArticle], *, lookback_days: int = 3) -> dict[str, int]:
    """Normalise + dedupe + insert. Returns counts. Clustering/analysis happen separately."""
    from .clustering import assign_story

    stats = {"seen": len(raws), "inserted": 0, "duplicates": 0, "old": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    recent = db.execute(select(Article).where(Article.fetched_at > datetime.now(timezone.utc) - timedelta(days=7))).scalars().all()
    for raw in raws:
        if not raw.url or not raw.title:
            continue
        norm = normalize(raw)
        if norm["published_at"] and norm["published_at"] < cutoff:
            stats["old"] += 1
            continue
        dup = find_duplicate(db, norm, recent=recent)
        if dup is not None:
            stats["duplicates"] += 1
            if dup.url_hash != norm["url_hash"]:
                # keep provenance for a syndicated copy, hidden behind the original
                src = _source_for(db, norm["url"], norm["publication"])
                copy = Article(**norm, source_id=src.id if src else None, duplicate_of_id=dup.id, story_id=dup.story_id)
                db.add(copy)
                db.flush()
            continue
        src = _source_for(db, norm["url"], norm["publication"])
        art = Article(**norm, source_id=src.id if src else None)
        db.add(art)
        db.flush()
        recent.append(art)
        assign_story(db, art)
        stats["inserted"] += 1
    db.commit()
    return stats


def run_ingest(db: Session, *, feed_ids: list[str] | None = None, analyze: bool = True, progress=None) -> dict[str, Any]:
    policy = NetworkPolicy.load(db)
    policy.check(locality="cloud", purpose="research", provider="news")
    ensure_default_feeds(db)
    news_cfg = settings_service.get(db, "news", {}) or {}
    limit = int(news_cfg.get("max_articles_per_feed", 40))
    lookback = int(news_cfg.get("lookback_days", 3))
    q = select(Feed).where(Feed.enabled.is_(True))
    if feed_ids:
        q = q.where(Feed.id.in_(feed_ids))
    feeds = db.execute(q).scalars().all()
    totals = {"feeds": len(feeds), "feeds_ok": 0, "feeds_failed": 0, "seen": 0, "inserted": 0, "duplicates": 0, "old": 0, "errors": []}
    for i, feed in enumerate(feeds):
        if progress:
            progress(i / max(1, len(feeds)), f"Fetching {feed.name}")
        try:
            raws = fetch_feed(db, feed, limit=limit)
            feed.last_error = None
            feed.fetch_count = (feed.fetch_count or 0) + 1
            feed.last_fetched_at = datetime.now(timezone.utc)
            totals["feeds_ok"] += 1
        except ProviderError as e:
            feed.last_error = str(e)[:500]
            totals["feeds_failed"] += 1
            totals["errors"].append({"feed": feed.name, "error": str(e)[:200]})
            db.commit()
            continue
        stats = ingest_raw_articles(db, raws, lookback_days=lookback)
        for k in ("seen", "inserted", "duplicates", "old"):
            totals[k] += stats[k]
        db.commit()
    if analyze:
        from .analysis import analyze_pending_stories

        if progress:
            progress(0.9, "Analysing stories")
        totals["analyzed"] = analyze_pending_stories(db, progress=progress)
    settings_service.set(db, "last_ingest", {"at": datetime.now(timezone.utc).isoformat(), **{k: v for k, v in totals.items() if k != "errors"}, "error_count": len(totals["errors"])})
    return totals


def touch_story(db: Session, story: Story, article: Article, description: str = "") -> None:
    story.last_updated = max(story.last_updated or article.fetched_at, article.published_at or article.fetched_at)
    db.add(StoryEvent(story_id=story.id, article_id=article.id, occurred_at=article.published_at or article.fetched_at, kind="article", description=description or f"{article.publication}: {article.title}"))
