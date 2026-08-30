from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PositionBrief, Principle, ThinkSession
from ..providers.base import ProviderError
from ..services import think as svc
from .common import d, dl, get_or_404

router = APIRouter(prefix="/think", tags=["think"])


class StartIn(BaseModel):
    title: str
    story_id: str | None = None
    principle_id: str | None = None
    question: str = ""
    ask_first_question: bool = True


class AnswerIn(BaseModel):
    text: str


@router.get("/sessions")
def list_sessions(status: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(ThinkSession)
    if status:
        q = q.where(ThinkSession.status == status)
    rows = db.execute(q.order_by(ThinkSession.updated_at.desc())).scalars().all()
    out = []
    for s in rows:
        row = d(s)
        row["exchanges"] = sum(1 for m in s.messages or [] if m.get("role") == "user")
        row["brief_ids"] = [b.id for b in s.briefs]
        out.append(row)
    return out


@router.post("/sessions", status_code=201)
def start(body: StartIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = svc.start_session(db, title=body.title, story_id=body.story_id, principle_id=body.principle_id, question=body.question)
    if body.ask_first_question:
        try:
            svc.next_question(db, s)
        except ProviderError as e:
            raise HTTPException(503, str(e)) from e
    return _session(db, s)


def _session(db: Session, s: ThinkSession) -> dict[str, Any]:
    out = d(s)
    out["briefs"] = dl(s.briefs)
    out["principles_considered"] = [{"id": p.id, "title": p.title, "category": p.category} for p in (db.get(Principle, i) for i in s.principle_ids_considered or []) if p]
    return out


@router.get("/sessions/{sid}")
def get_session(sid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _session(db, get_or_404(db, ThinkSession, sid))


@router.post("/sessions/{sid}/answer")
def answer(sid: str, body: AnswerIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = get_or_404(db, ThinkSession, sid)
    if s.status not in ("active",):
        raise HTTPException(400, "session is not active")
    svc.answer(db, s, body.text)
    try:
        svc.next_question(db, s)
    except ProviderError as e:
        raise HTTPException(503, str(e)) from e
    return _session(db, s)


@router.post("/sessions/{sid}/brief")
def make_brief(sid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = get_or_404(db, ThinkSession, sid)
    try:
        b = svc.generate_brief(db, s)
    except ProviderError as e:
        raise HTTPException(503, str(e)) from e
    return d(b)


@router.post("/sessions/{sid}/abandon")
def abandon(sid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = get_or_404(db, ThinkSession, sid)
    s.status = "abandoned"
    db.commit()
    return d(s)


@router.get("/briefs")
def list_briefs(status: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(PositionBrief)
    if status:
        q = q.where(PositionBrief.status == status)
    return dl(db.execute(q.order_by(PositionBrief.created_at.desc())).scalars())


@router.get("/briefs/{bid}")
def get_brief(bid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    b = get_or_404(db, PositionBrief, bid)
    out = d(b)
    out["markdown"] = svc.brief_to_markdown(b)
    return out


class BriefPatch(BaseModel):
    issue: str | None = None
    position: str | None = None
    rationale: str | None = None
    strongest_for: str | None = None
    strongest_against: str | None = None
    response: str | None = None
    factual_assumptions: list[str] | None = None
    unresolved_questions: list[str] | None = None
    policy_mechanisms: list[str] | None = None
    confidence: float | None = None
    governing_principle_id: str | None = None


@router.patch("/briefs/{bid}")
def patch_brief(bid: str, body: BriefPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    b = get_or_404(db, PositionBrief, bid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(b, k, v)
    db.commit()
    return d(b)


class ApproveIn(BaseModel):
    mode: str = "auto"  # auto | revise | new
    principle_id: str | None = None
    title: str | None = None
    category: str | None = None
    reason: str = ""


@router.post("/briefs/{bid}/approve")
def approve(bid: str, body: ApproveIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    b = get_or_404(db, PositionBrief, bid)
    p = svc.approve_brief(db, b, mode=body.mode, principle_id=body.principle_id, title=body.title, category=body.category, reason=body.reason)
    return {"brief": d(b), "principle": d(p)}
