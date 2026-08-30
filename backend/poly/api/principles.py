from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ContentItem, Counterargument, PositionBrief, Principle, PrincipleRevision, StoryPrincipleLink, SupportingEvidence
from ..services import principles as svc
from ..services.search import embed_entity
from .common import d, dl, get_or_404

router = APIRouter(prefix="/principles", tags=["principles"])


class PrincipleIn(BaseModel):
    title: str
    category: str
    current_position: str
    rationale: str = ""
    status: str = "provisional"
    confidence: float = 0.6
    sort_order: int = 0


class PrincipleUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    current_position: str | None = None
    rationale: str | None = None
    status: str | None = None
    confidence: float | None = None
    sort_order: int | None = None
    reason_for_change: str = ""


class EvidenceIn(BaseModel):
    source: str = ""
    source_type: str = "secondary"
    summary: str = ""
    url: str = ""
    publication_date: str | None = None
    reliability: str = "unknown"
    notes: str = ""
    article_id: str | None = None


class CounterIn(BaseModel):
    argument: str
    source: str = ""
    strength: str = "moderate"
    response: str = ""
    unresolved_questions: list[str] = []


@router.get("")
def list_principles(category: str | None = None, status: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = svc.list_principles(db, category=category, status=status)
    out = []
    for p in rows:
        item = d(p)
        item["evidence_count"] = len(p.evidence)
        item["counterargument_count"] = len(p.counterarguments)
        item["revision_count"] = len(p.revisions)
        item["story_count"] = len(p.story_links)
        out.append(item)
    return out


@router.get("/categories")
def categories(db: Session = Depends(get_db)) -> list[str]:
    return sorted({p.category for p in db.execute(select(Principle)).scalars()})


@router.post("", status_code=201)
def create(body: PrincipleIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = svc.create_principle(db, body.model_dump())
    db.add(PrincipleRevision(principle_id=p.id, old_position="", new_position=p.current_position, new_status=p.status, reason_for_change="Created"))
    db.commit()
    embed_entity(db, "principle", p)
    return d(p)


@router.get("/{pid}")
def get_principle(pid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = get_or_404(db, Principle, pid)
    out = d(p)
    out["revisions"] = dl(p.revisions)
    out["evidence"] = dl(p.evidence)
    out["counterarguments"] = dl(p.counterarguments)
    links = db.execute(select(StoryPrincipleLink).where(StoryPrincipleLink.principle_id == pid)).scalars().all()
    out["stories"] = [{"story_id": l.story_id, "title": l.story.title, "relation": l.relation, "strength": l.strength, "last_updated": l.story.last_updated.isoformat()} for l in links]
    content = db.execute(select(ContentItem)).scalars().all()
    out["content"] = [{"id": c.id, "title": c.title, "format": c.format, "status": c.status} for c in content if pid in (c.principle_ids or [])]
    briefs = db.execute(select(PositionBrief).where((PositionBrief.governing_principle_id == pid) | (PositionBrief.approved_principle_id == pid))).scalars().all()
    out["briefs"] = [{"id": b.id, "issue": b.issue, "status": b.status, "created_at": b.created_at.isoformat()} for b in briefs]
    return out


@router.patch("/{pid}")
def update(pid: str, body: PrincipleUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = get_or_404(db, Principle, pid)
    data = body.model_dump(exclude_none=True)
    reason = data.pop("reason_for_change", "")
    p = svc.update_principle(db, p, data, reason=reason)
    embed_entity(db, "principle", p)
    return d(p)


@router.delete("/{pid}", status_code=204)
def delete(pid: str, db: Session = Depends(get_db)) -> None:
    p = get_or_404(db, Principle, pid)
    p.status = "retired"
    db.add(PrincipleRevision(principle_id=p.id, old_position=p.current_position, new_position=p.current_position, old_status=p.status, new_status="retired", reason_for_change="Retired"))
    db.commit()


@router.post("/{pid}/evidence", status_code=201)
def add_evidence(pid: str, body: EvidenceIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    from dateutil import parser as dp

    p = get_or_404(db, Principle, pid)
    data = body.model_dump()
    if data.get("publication_date"):
        try:
            data["publication_date"] = dp.parse(data["publication_date"])
        except (ValueError, TypeError):
            data["publication_date"] = None
    return d(svc.add_evidence(db, p, data))


@router.delete("/{pid}/evidence/{eid}", status_code=204)
def del_evidence(pid: str, eid: str, db: Session = Depends(get_db)) -> None:
    ev = get_or_404(db, SupportingEvidence, eid)
    db.delete(ev)
    db.commit()


@router.post("/{pid}/counterarguments", status_code=201)
def add_counter(pid: str, body: CounterIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = get_or_404(db, Principle, pid)
    return d(svc.add_counterargument(db, p, body.model_dump()))


@router.patch("/{pid}/counterarguments/{cid}")
def update_counter(pid: str, cid: str, body: CounterIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    ca = get_or_404(db, Counterargument, cid)
    for k, v in body.model_dump().items():
        setattr(ca, k, v)
    db.commit()
    return d(ca)


@router.delete("/{pid}/counterarguments/{cid}", status_code=204)
def del_counter(pid: str, cid: str, db: Session = Depends(get_db)) -> None:
    ca = get_or_404(db, Counterargument, cid)
    db.delete(ca)
    db.commit()


@router.post("/import")
def import_md(db: Session = Depends(get_db)) -> dict[str, int]:
    res = svc.import_markdown(db)
    for p in svc.list_principles(db):
        embed_entity(db, "principle", p)
    return res


@router.post("/export")
def export_md(db: Session = Depends(get_db)) -> dict[str, str]:
    return {"path": str(svc.export_markdown(db))}


@router.get("/export/markdown")
def export_md_text(db: Session = Depends(get_db)) -> dict[str, str]:
    return {"markdown": svc.to_markdown(svc.list_principles(db))}
