from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..jobs.tasks import enqueue
from ..models import (
    Article,
    BookNote,
    Claim,
    ContentItem,
    Feed,
    ResearchNote,
    Source,
    Story,
    StoryEvent,
    ThinkSession,
)
from ..services import settings as settings_service
from ..services.clustering import merge_stories
from ..services.ingest import ensure_default_feeds
from ..services.search import embed_entity
from .common import d, dl, get_or_404

router = APIRouter(tags=["stories"])
ACTIONS = {"none", "ignored", "research", "develop_position", "create_content", "save_for_book"}


def _story_summary(s: Story) -> dict[str, Any]:
    out = d(s)
    arts = [a for a in s.articles if not a.duplicate_of_id]
    out["article_count"] = len(arts)
    out["duplicate_count"] = len(s.articles) - len(arts)
    out["publications"] = sorted({a.publication for a in arts})[:8]
    out["principles"] = [{"id": l.principle_id, "title": l.principle.title, "relation": l.relation, "strength": l.strength, "note": l.note} for l in sorted(s.principle_links, key=lambda l: -l.strength)]
    out["claim_count"] = len(s.claims)
    return out


@router.get("/stories")
def list_stories(status: str | None = None, topic: str | None = None, days: int = 14, min_relevance: float = 0.0, action: str | None = None, limit: int = 100, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    since = datetime.now(UTC) - timedelta(days=days)
    q = select(Story).where(Story.last_updated >= since)
    if status:
        q = q.where(Story.status == status)
    if action:
        q = q.where(Story.dashboard_action == action)
    rows = db.execute(q.order_by(Story.last_updated.desc()).limit(limit * 2)).scalars().all()
    out = []
    for s in rows:
        if topic and topic not in (s.topics or []):
            continue
        if s.relevance_score < min_relevance:
            continue
        out.append(_story_summary(s))
    return out[:limit]


@router.get("/stories/{sid}")
def get_story(sid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = get_or_404(db, Story, sid)
    out = _story_summary(s)
    arts = sorted(s.articles, key=lambda a: a.published_at or a.fetched_at, reverse=True)
    out["articles"] = []
    for a in arts:
        row = d(a)
        row.pop("content", None)
        row.pop("raw", None)
        row["source"] = d(a.source) if a.source else None
        out["articles"].append(row)
    out["claims"] = dl(s.claims)
    out["events"] = dl(s.events)
    out["think_sessions"] = [{"id": t.id, "title": t.title, "status": t.status, "created_at": t.created_at.isoformat()} for t in db.execute(select(ThinkSession).where(ThinkSession.story_id == sid)).scalars()]
    out["content"] = [{"id": c.id, "title": c.title, "format": c.format, "status": c.status} for c in db.execute(select(ContentItem).where(ContentItem.story_id == sid)).scalars()]
    out["notes"] = dl(db.execute(select(ResearchNote).where(ResearchNote.story_id == sid)).scalars())
    out["book_notes"] = dl(db.execute(select(BookNote).where(BookNote.story_id == sid)).scalars())
    return out


class ActionIn(BaseModel):
    action: str


@router.post("/stories/{sid}/action")
def set_action(sid: str, body: ActionIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.action not in ACTIONS:
        raise HTTPException(400, "bad action")
    s = get_or_404(db, Story, sid)
    s.dashboard_action = body.action
    if body.action == "ignored":
        s.status = "ignored"
    elif s.status == "ignored":
        s.status = "developing"
    db.add(StoryEvent(story_id=s.id, kind="user", description=f"Action: {body.action.replace('_', ' ')}"))
    db.commit()
    return _story_summary(s)


@router.post("/stories/{sid}/analyze")
def analyze(sid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_or_404(db, Story, sid)
    return d(enqueue(db, "analyze_story", {"story_id": sid}))


class MergeIn(BaseModel):
    other_story_id: str


@router.post("/stories/{sid}/merge")
def merge(sid: str, body: MergeIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    a = get_or_404(db, Story, sid)
    b = get_or_404(db, Story, body.other_story_id)
    return _story_summary(merge_stories(db, a, b))


class ClaimPatch(BaseModel):
    verification_status: str | None = None
    notes: str | None = None
    claim_type: str | None = None
    primary_source_url: str | None = None


@router.patch("/claims/{cid}")
def patch_claim(cid: str, body: ClaimPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = get_or_404(db, Claim, cid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    return d(c)


@router.get("/articles/{aid}")
def get_article(aid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    a = get_or_404(db, Article, aid)
    out = d(a)
    out["source"] = d(a.source) if a.source else None
    return out


# ---- feeds / sources ----
@router.get("/feeds")
def list_feeds(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    ensure_default_feeds(db)
    rows = db.execute(select(Feed).order_by(Feed.category, Feed.name)).scalars().all()
    out = []
    for f in rows:
        row = d(f)
        src = db.get(Source, f.source_id) if f.source_id else None
        row["source"] = d(src) if src else None
        row["article_count"] = db.query(Article).filter(Article.feed_id == f.id).count()
        out.append(row)
    return out


class FeedIn(BaseModel):
    name: str
    url: str
    provider: str = "rss"
    query: str | None = None
    category: str = "general"
    enabled: bool = True


class FeedPatch(BaseModel):
    name: str | None = None
    url: str | None = None
    category: str | None = None
    enabled: bool | None = None
    query: str | None = None


@router.post("/feeds", status_code=201)
def add_feed(body: FeedIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    f = Feed(**body.model_dump())
    db.add(f)
    db.commit()
    db.refresh(f)
    return d(f)


@router.patch("/feeds/{fid}")
def patch_feed(fid: str, body: FeedPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    f = get_or_404(db, Feed, fid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(f, k, v)
    db.commit()
    return d(f)


@router.delete("/feeds/{fid}", status_code=204)
def del_feed(fid: str, db: Session = Depends(get_db)) -> None:
    f = get_or_404(db, Feed, fid)
    db.delete(f)
    db.commit()


@router.post("/feeds/{fid}/fetch")
def fetch_feed_now(fid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_or_404(db, Feed, fid)
    return d(enqueue(db, "ingest", {"feed_ids": [fid]}))


@router.post("/ingest/run")
def run_ingest_now(db: Session = Depends(get_db)) -> dict[str, Any]:
    return d(enqueue(db, "ingest", {"trigger": "manual"}))


@router.get("/ingest/status")
def ingest_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..providers.news.apis import provider_status

    return {"last_ingest": settings_service.get(db, "last_ingest", {}) or {}, "providers": provider_status(), "story_count": db.query(Story).count(), "article_count": db.query(Article).count()}


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return dl(db.execute(select(Source).order_by(Source.name)).scalars())


class SourcePatch(BaseModel):
    source_type: str | None = None
    is_primary: bool | None = None
    ideology: str | None = None
    reliability_notes: str | None = None


@router.patch("/sources/{sid}")
def patch_source(sid: str, body: SourcePatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = get_or_404(db, Source, sid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.commit()
    return d(s)


# ---- research notes ----
class NoteIn(BaseModel):
    title: str
    body: str = ""
    kind: str = "note"
    tags: list[str] = []
    story_id: str | None = None
    principle_id: str | None = None
    content_item_id: str | None = None


@router.get("/research")
def list_notes(story_id: str | None = None, principle_id: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(ResearchNote)
    if story_id:
        q = q.where(ResearchNote.story_id == story_id)
    if principle_id:
        q = q.where(ResearchNote.principle_id == principle_id)
    return dl(db.execute(q.order_by(ResearchNote.updated_at.desc())).scalars())


@router.post("/research", status_code=201)
def create_note(body: NoteIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    n = ResearchNote(**body.model_dump())
    db.add(n)
    db.commit()
    db.refresh(n)
    embed_entity(db, "research_note", n)
    return d(n)


@router.patch("/research/{nid}")
def update_note(nid: str, body: NoteIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    n = get_or_404(db, ResearchNote, nid)
    for k, v in body.model_dump().items():
        setattr(n, k, v)
    db.commit()
    embed_entity(db, "research_note", n)
    return d(n)


@router.delete("/research/{nid}", status_code=204)
def delete_note(nid: str, db: Session = Depends(get_db)) -> None:
    n = get_or_404(db, ResearchNote, nid)
    db.delete(n)
    db.commit()
