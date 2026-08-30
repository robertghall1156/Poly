from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BookChapter, BookNote, BookProject, ContentItem, Principle, Story, Video
from ..services.search import embed_entity
from .common import d, dl, get_or_404

router = APIRouter(prefix="/book", tags=["book"])


def ensure_default_book(db: Session) -> BookProject:
    b = db.execute(select(BookProject).order_by(BookProject.created_at)).scalars().first()
    if b is None:
        b = BookProject(title="Untitled book", working_titles=["The System We Inherited"], premise="Why the system works the way it does — and what would change it.")
        db.add(b)
        db.commit()
        db.refresh(b)
    return b


class BookIn(BaseModel):
    title: str | None = None
    working_titles: list[str] | None = None
    premise: str | None = None
    status: str | None = None


@router.get("")
def list_books(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    ensure_default_book(db)
    rows = db.execute(select(BookProject).order_by(BookProject.created_at)).scalars().all()
    out = []
    for b in rows:
        row = d(b)
        row["chapter_count"] = len(b.chapters)
        row["note_count"] = len(b.notes)
        out.append(row)
    return out


@router.post("", status_code=201)
def create_book(body: BookIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    b = BookProject(title=body.title or "Untitled book", working_titles=body.working_titles or [], premise=body.premise or "", status=body.status or "concept")
    db.add(b)
    db.commit()
    return d(b)


@router.get("/{bid}")
def get_book(bid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    b = get_or_404(db, BookProject, bid)
    out = d(b)
    out["chapters"] = [dict(d(c), note_count=len(c.notes)) for c in b.chapters]
    notes = []
    for n in sorted(b.notes, key=lambda n: n.created_at, reverse=True):
        row = d(n)
        row["links"] = _links(db, n)
        notes.append(row)
    out["notes"] = notes
    return out


def _links(db: Session, n: BookNote) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if n.story_id and (s := db.get(Story, n.story_id)):
        out["story"] = {"id": s.id, "title": s.title}
    if n.principle_id and (p := db.get(Principle, n.principle_id)):
        out["principle"] = {"id": p.id, "title": p.title}
    if n.content_item_id and (c := db.get(ContentItem, n.content_item_id)):
        out["content"] = {"id": c.id, "title": c.title, "format": c.format}
    if n.video_id and (v := db.get(Video, n.video_id)):
        out["video"] = {"id": v.id, "filename": v.filename}
    return out


@router.patch("/{bid}")
def patch_book(bid: str, body: BookIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    b = get_or_404(db, BookProject, bid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(b, k, v)
    db.commit()
    return d(b)


class ChapterIn(BaseModel):
    title: str
    summary: str = ""
    order: int = 0
    body: str = ""
    status: str = "idea"


@router.post("/{bid}/chapters", status_code=201)
def add_chapter(bid: str, body: ChapterIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_or_404(db, BookProject, bid)
    c = BookChapter(book_id=bid, **body.model_dump())
    db.add(c)
    db.commit()
    return d(c)


@router.patch("/chapters/{cid}")
def patch_chapter(cid: str, body: ChapterIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = get_or_404(db, BookChapter, cid)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return d(c)


@router.delete("/chapters/{cid}", status_code=204)
def del_chapter(cid: str, db: Session = Depends(get_db)) -> None:
    c = get_or_404(db, BookChapter, cid)
    db.delete(c)
    db.commit()


class NoteIn(BaseModel):
    title: str
    body: str = ""
    kind: str = "note"
    book_id: str | None = None
    chapter_id: str | None = None
    story_id: str | None = None
    principle_id: str | None = None
    content_item_id: str | None = None
    video_id: str | None = None
    article_id: str | None = None


@router.post("/notes", status_code=201)
def add_note(body: NoteIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """`Save to Book` from anywhere: pass the linked entity ids."""
    data = body.model_dump()
    if not data.get("book_id"):
        data["book_id"] = ensure_default_book(db).id
    n = BookNote(**data)
    db.add(n)
    db.commit()
    db.refresh(n)
    embed_entity(db, "book_note", n)
    return d(n)


@router.get("/notes")
def list_notes(kind: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(BookNote)
    if kind:
        q = q.where(BookNote.kind == kind)
    return dl(db.execute(q.order_by(BookNote.created_at.desc())).scalars())


@router.patch("/notes/{nid}")
def patch_note(nid: str, body: NoteIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    n = get_or_404(db, BookNote, nid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(n, k, v)
    db.commit()
    embed_entity(db, "book_note", n)
    return d(n)


@router.delete("/notes/{nid}", status_code=204)
def del_note(nid: str, db: Session = Depends(get_db)) -> None:
    n = get_or_404(db, BookNote, nid)
    db.delete(n)
    db.commit()
