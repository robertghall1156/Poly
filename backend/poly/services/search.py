"""Embeddings + hybrid search (keyword LIKE/FTS + cosine similarity).

Every searchable entity is chunked, embedded with the best available *local* embedding model
(hashing fallback when none), and stored in `embeddings`. Search combines a keyword score with a
vector score using reciprocal-rank fusion.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import (
    Article,
    BookNote,
    Clip,
    ContentItem,
    Embedding,
    PositionBrief,
    Principle,
    ResearchNote,
    Story,
    TranscriptSegment,
    Video,
)
from ..providers.registry import Router

CHUNK_CHARS = 1200
ENTITY_MODELS = {
    "principle": Principle,
    "article": Article,
    "story": Story,
    "research_note": ResearchNote,
    "transcript_segment": TranscriptSegment,
    "clip": Clip,
    "content_item": ContentItem,
    "book_note": BookNote,
    "position_brief": PositionBrief,
    "video": Video,
}


def entity_text(entity_type: str, obj: Any) -> str:
    if entity_type == "principle":
        return f"{obj.title}\n{obj.category}\n{obj.current_position}\n{obj.rationale}"
    if entity_type == "article":
        return f"{obj.title}\n{obj.summary}\n{(obj.content or '')[:6000]}"
    if entity_type == "story":
        return f"{obj.title}\n{obj.summary}\n{obj.why_it_matters}\n{' '.join(obj.topics or [])}"
    if entity_type == "research_note":
        return f"{obj.title}\n{obj.body}"
    if entity_type == "transcript_segment":
        return obj.text
    if entity_type == "clip":
        return f"{obj.title}\n{obj.caption}\n{obj.transcript_text}"
    if entity_type == "content_item":
        return f"{obj.title}\n{obj.script[:8000]}"
    if entity_type == "book_note":
        return f"{obj.title}\n{obj.body}"
    if entity_type == "position_brief":
        return f"{obj.issue}\n{obj.position}\n{obj.rationale}\n{obj.strongest_for}\n{obj.strongest_against}"
    if entity_type == "video":
        return f"{obj.filename}\n{obj.summary}\n{' '.join(obj.topics or [])}"
    return ""


def entity_title(entity_type: str, obj: Any) -> str:
    for attr in ("title", "issue", "filename", "text"):
        v = getattr(obj, attr, None)
        if v:
            return str(v)[:200]
    return entity_type


def chunk(text: str, size: int = CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    parts, buf = [], ""
    for para in re.split(r"\n{2,}|(?<=[.!?])\s+", text):
        if len(buf) + len(para) + 1 > size and buf:
            parts.append(buf.strip())
            buf = ""
        buf += para + " "
    if buf.strip():
        parts.append(buf.strip())
    return parts


def embed_entity(db: Session, entity_type: str, obj: Any, router: Router | None = None) -> int:
    router = router or Router(db)
    text = entity_text(entity_type, obj)
    chunks = chunk(text)
    db.query(Embedding).filter(Embedding.entity_type == entity_type, Embedding.entity_id == obj.id).delete()
    if not chunks:
        db.commit()
        return 0
    vectors, model = router.embed(chunks)
    for i, (c, v) in enumerate(zip(chunks, vectors)):
        db.add(Embedding(entity_type=entity_type, entity_id=obj.id, chunk_index=i, text=c[:4000], model=model, vector=v))
    db.commit()
    return len(chunks)


def reembed_stale(db: Session, *, limit: int = 500) -> int:
    """Re-embed chunks made with the hashing fallback once a real model exists."""
    router = Router(db)
    _, model = router.embedding_model()
    if model == "hashing-v1":
        return 0
    stale = db.execute(select(Embedding).where(Embedding.model != model).limit(limit)).scalars().all()
    done = set()
    for e in stale:
        key = (e.entity_type, e.entity_id)
        if key in done:
            continue
        model_cls = ENTITY_MODELS.get(e.entity_type)
        obj = db.get(model_cls, e.entity_id) if model_cls else None
        if obj is not None:
            embed_entity(db, e.entity_type, obj, router)
        done.add(key)
    return len(done)


@dataclass
class SearchHit:
    entity_type: str
    entity_id: str
    title: str
    snippet: str
    score: float
    keyword_rank: int | None = None
    vector_rank: int | None = None
    meta: dict[str, Any] | None = None


def _keyword_hits(db: Session, query: str, types: list[str], limit: int) -> list[tuple[str, str, str, str]]:
    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2][:6]
    if not terms:
        return []
    hits: list[tuple[str, str, str, str]] = []
    for etype in types:
        model = ENTITY_MODELS.get(etype)
        if model is None:
            continue
        cols = [c for c in (getattr(model, "title", None), getattr(model, "text", None), getattr(model, "summary", None), getattr(model, "current_position", None), getattr(model, "body", None), getattr(model, "issue", None), getattr(model, "position", None), getattr(model, "filename", None), getattr(model, "script", None)) if c is not None]
        if not cols:
            continue
        conds = [c.ilike(f"%{t}%") for t in terms for c in cols]
        rows = db.execute(select(model).where(or_(*conds)).limit(limit * 3)).scalars().all()
        for r in rows:
            text = entity_text(etype, r).lower()
            score = sum(text.count(t) for t in terms)
            hits.append((etype, r.id, entity_title(etype, r), text[:300]))
            hits[-1] = (*hits[-1][:3], f"{score:06d}|" + hits[-1][3])
    hits.sort(key=lambda h: h[3], reverse=True)
    return [(a, b, c, d.split("|", 1)[1]) for a, b, c, d in hits[:limit]]


def _vector_hits(db: Session, query: str, types: list[str], limit: int, router: Router) -> list[tuple[str, str, float, str]]:
    (qv,), model = router.embed([query])
    q = np.asarray(qv, dtype=np.float32)
    engine = db.get_bind()
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text as sqltext

        vec_literal = "[" + ",".join(f"{x:.6f}" for x in q.tolist()) + "]"
        rows = db.execute(
            sqltext(
                "SELECT entity_type, entity_id, text, 1 - (vector <=> CAST(:q AS vector)) AS sim FROM embeddings "
                "WHERE entity_type = ANY(:types) ORDER BY vector <=> CAST(:q AS vector) LIMIT :lim"
            ),
            {"q": vec_literal, "types": types, "lim": limit},
        ).all()
        return [(r[0], r[1], float(r[3]), r[2]) for r in rows]
    rows = db.execute(select(Embedding).where(Embedding.entity_type.in_(types))).scalars().all()
    if not rows:
        return []
    mat = np.asarray([r.vector for r in rows if r.vector], dtype=np.float32)
    valid = [r for r in rows if r.vector]
    if mat.size == 0:
        return []
    norms = np.linalg.norm(mat, axis=1) * (np.linalg.norm(q) or 1.0)
    sims = mat @ q / np.where(norms == 0, 1, norms)
    best: dict[tuple[str, str], tuple[float, str]] = {}
    for r, s in zip(valid, sims):
        key = (r.entity_type, r.entity_id)
        if key not in best or s > best[key][0]:
            best[key] = (float(s), r.text)
    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    return [(k[0], k[1], v[0], v[1]) for k, v in ranked]


def search(db: Session, query: str, *, types: list[str] | None = None, limit: int = 20, router: Router | None = None) -> list[SearchHit]:
    query = query.strip()
    if not query:
        return []
    types = types or list(ENTITY_MODELS.keys())
    router = router or Router(db)
    kw = _keyword_hits(db, query, types, limit * 2)
    vec = _vector_hits(db, query, types, limit * 2, router)
    fused: dict[tuple[str, str], SearchHit] = {}
    k = 60.0
    for rank, (etype, eid, title, snippet) in enumerate(kw):
        hit = fused.setdefault((etype, eid), SearchHit(etype, eid, title, snippet, 0.0))
        hit.score += 1.0 / (k + rank)
        hit.keyword_rank = rank
    for rank, (etype, eid, sim, snippet) in enumerate(vec):
        if sim < 0.05:
            continue
        hit = fused.get((etype, eid))
        if hit is None:
            model = ENTITY_MODELS[etype]
            obj = db.get(model, eid)
            if obj is None:
                continue
            hit = fused.setdefault((etype, eid), SearchHit(etype, eid, entity_title(etype, obj), snippet[:300], 0.0))
        hit.score += 1.0 / (k + rank) * (1.0 + sim)
        hit.vector_rank = rank
    hits = sorted(fused.values(), key=lambda h: h.score, reverse=True)[:limit]
    for h in hits:
        model = ENTITY_MODELS[h.entity_type]
        obj = db.get(model, h.entity_id)
        h.meta = _meta(h.entity_type, obj)
    return hits


def _meta(etype: str, obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if etype == "transcript_segment":
        return {"video_id": obj.video_id, "start": obj.start, "end": obj.end}
    if etype == "clip":
        return {"video_id": obj.video_id, "start": obj.start, "end": obj.end}
    if etype == "article":
        return {"story_id": obj.story_id, "url": obj.url, "publication": obj.publication}
    if etype == "principle":
        return {"category": obj.category, "status": obj.status}
    if etype == "content_item":
        return {"format": obj.format, "status": obj.status}
    if etype == "story":
        return {"status": obj.status, "relevance": obj.relevance_score}
    return {}


def cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db_ = math.sqrt(sum(y * y for y in b)) or 1.0
    return num / (da * db_)
