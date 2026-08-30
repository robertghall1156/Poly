"""Story clustering.

An article joins an existing *recent* story when its title/summary is similar enough
(term-frequency cosine over keyword tokens, boosted by shared named-entity-like capitalised terms and
shared topics); otherwise it starts a new story. This is deterministic, fast, and needs no model.
The LLM later refines story titles/summaries during analysis.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Article, Story, StoryEvent

STOPWORDS = set(
    """a an the and or but of to in on at for with by from as is are was were be been being this that these those it its
    into over under after before about against between during without within than then so such not no nor
    he she they them his her their we our you your i me my who whom which what when where why how will would
    can could should may might must new says said say according amid among across up down out off more most
    less least very just also still yet even only own same too here there again ever never now today""".split()
)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")
CLUSTER_WINDOW_DAYS = 5
JOIN_THRESHOLD = 0.32


def tokens(text: str) -> list[str]:
    return [w.lower().strip("'-") for w in _WORD.findall(text or "") if w.lower() not in STOPWORDS and len(w) > 2]


def keywords(text: str, n: int = 12) -> list[str]:
    counts = Counter(tokens(text))
    return [w for w, _ in counts.most_common(n)]


def entities(text: str) -> set[str]:
    """Crude named-entity proxy: capitalised tokens not at sentence start."""
    out = set()
    for sent in re.split(r"(?<=[.!?])\s+", text or ""):
        words = _WORD.findall(sent)
        for w in words[1:]:
            if w[0].isupper() and w.lower() not in STOPWORDS and len(w) > 2:
                out.add(w.lower())
    return out


def _tf_vectors(docs: list[list[str]]) -> list[dict[str, float]]:
    """Log-scaled term-frequency vectors (unit length). IDF is deliberately not computed across a
    pair of documents — with two docs it punishes exactly the shared terms we care about."""
    vecs = []
    for d in docs:
        tf = Counter(d)
        v = {w: 1 + math.log(c) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({w: x / norm for w, x in v.items()})
    return vecs


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def similarity(article_text: str, article_topics: list[str], story_text: str, story_topics: list[str]) -> float:
    ta, ts = tokens(article_text), tokens(story_text)
    if not ta or not ts:
        return 0.0
    va, vs = _tf_vectors([ta, ts])
    sim = cosine(va, vs)
    ea, es = entities(article_text), entities(story_text)
    if ea and es:
        jac = len(ea & es) / len(ea | es)
        sim = 0.75 * sim + 0.25 * jac
    if article_topics and story_topics:
        overlap = len(set(article_topics) & set(story_topics)) / len(set(article_topics) | set(story_topics))
        sim += 0.1 * overlap
    return sim


def _story_text(story: Story) -> str:
    parts = [story.title, story.summary or ""]
    parts += [a.title for a in story.articles[:8]]
    return " ".join(parts)


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:80]


def assign_story(db: Session, article: Article, *, threshold: float = JOIN_THRESHOLD) -> Story:
    """Attach an article to the best matching recent story or create a new one."""
    from .ingest import touch_story

    text = f"{article.title}. {article.summary}"
    since = datetime.now(UTC) - timedelta(days=CLUSTER_WINDOW_DAYS)
    recent = db.execute(select(Story).where(Story.last_updated >= since, Story.status != "ignored")).scalars().all()
    best, best_sim = None, 0.0
    for story in recent:
        sim = similarity(text, article.topics or [], _story_text(story), story.topics or [])
        if sim > best_sim:
            best, best_sim = story, sim
    if best is not None and best_sim >= threshold:
        article.story_id = best.id
        best.status = "continuing" if best.analysis_version else "developing"
        kw = set(best.keywords or [])
        kw.update(keywords(text, 6))
        best.keywords = sorted(kw)[:30]
        topics = list(best.topics or [])
        for t in article.topics or []:
            if t not in topics:
                topics.append(t)
        best.topics = topics[:8]
        touch_story(db, best, article)
        db.flush()
        return best
    story = Story(
        title=article.title,
        slug=_slug(article.title),
        summary=article.summary[:600],
        status="new",
        first_seen=article.published_at or article.fetched_at,
        last_updated=article.published_at or article.fetched_at,
        topics=list(article.topics or []),
        keywords=keywords(text, 12),
    )
    db.add(story)
    db.flush()
    article.story_id = story.id
    db.add(StoryEvent(story_id=story.id, article_id=article.id, occurred_at=story.first_seen, kind="article", description=f"First seen: {article.publication}: {article.title}"))
    db.flush()
    return story


def merge_stories(db: Session, target: Story, other: Story) -> Story:
    for a in list(other.articles):
        a.story_id = target.id
    for e in list(other.events):
        e.story_id = target.id
    target.topics = sorted(set(target.topics or []) | set(other.topics or []))
    target.first_seen = min(target.first_seen, other.first_seen)
    target.last_updated = max(target.last_updated, other.last_updated)
    db.delete(other)
    db.commit()
    return target
