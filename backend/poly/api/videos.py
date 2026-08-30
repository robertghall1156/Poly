from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..jobs.tasks import enqueue
from ..models import Clip, ContentItem, TranscriptSegment, Video, VideoFolder
from ..services import media as svc
from .common import d, dl, get_or_404

router = APIRouter(prefix="/videos", tags=["videos"])


class FolderIn(BaseModel):
    path: str
    recursive: bool = True


@router.get("/folders")
def list_folders(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(VideoFolder).order_by(VideoFolder.created_at)).scalars().all()
    out = []
    for f in rows:
        row = d(f)
        row["video_count"] = len(f.videos)
        row["exists"] = Path(f.path).is_dir()
        out.append(row)
    return out


@router.post("/folders", status_code=201)
def add_folder(body: FolderIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        f = svc.add_folder(db, body.path, recursive=body.recursive)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e)) from e
    job = enqueue(db, "scan_folder", {"folder_id": f.id})
    return {"folder": d(f), "job": d(job)}


@router.post("/folders/{fid}/scan")
def scan(fid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_or_404(db, VideoFolder, fid)
    return d(enqueue(db, "scan_folder", {"folder_id": fid}))


@router.delete("/folders/{fid}", status_code=204)
def remove_folder(fid: str, db: Session = Depends(get_db)) -> None:
    f = get_or_404(db, VideoFolder, fid)
    db.delete(f)
    db.commit()


@router.get("")
def list_videos(folder_id: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(Video)
    if folder_id:
        q = q.where(Video.folder_id == folder_id)
    rows = db.execute(q.order_by(Video.file_created_at.desc().nulls_last())).scalars().all()
    out = []
    for v in rows:
        row = d(v)
        row["clip_count"] = len(v.clips)
        row["segment_count"] = len(v.segments)
        out.append(row)
    return out


@router.get("/clips/recent")
def recent_clips(limit: int = 12, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(Clip).where(Clip.status != "dismissed").order_by(Clip.created_at.desc(), Clip.score.desc()).limit(limit)).scalars().all()
    out = []
    for c in rows:
        row = d(c)
        row["video_filename"] = c.video.filename
        out.append(row)
    return out


@router.get("/{vid}")
def get_video(vid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    v = get_or_404(db, Video, vid)
    out = d(v)
    out["segments"] = dl(v.segments)
    out["clips"] = dl(sorted(v.clips, key=lambda c: -c.score))
    out["exists"] = Path(v.path).exists()
    out["content"] = [{"id": c.id, "title": c.title, "format": c.format} for c in db.execute(select(ContentItem).where(ContentItem.source_video_id == vid)).scalars()]
    return out


@router.post("/{vid}/transcribe")
def transcribe(vid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    v = get_or_404(db, Video, vid)
    if not Path(v.path).exists():
        raise HTTPException(400, "video file is missing")
    v.transcript_status = "queued"
    db.commit()
    return d(enqueue(db, "transcribe", {"video_id": vid}))


class TranscriptIn(BaseModel):
    segments: list[dict[str, Any]]
    language: str = "en"
    provider: str = "import"


@router.post("/{vid}/transcript")
def import_transcript(vid: str, body: TranscriptIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Import an existing transcript (e.g. from another local tool). Each segment: {start,end,text,words?}."""
    v = get_or_404(db, Video, vid)
    svc.save_transcript(db, v, body.segments, language=body.language, provider=body.provider)
    return {"segments": len(v.segments)}


@router.post("/{vid}/clips/discover")
def discover(vid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    v = get_or_404(db, Video, vid)
    if v.transcript_status != "done":
        raise HTTPException(400, "transcribe the video first")
    return d(enqueue(db, "discover_clips", {"video_id": vid}))


class ClipIn(BaseModel):
    start: float
    end: float
    title: str = ""
    caption: str = ""
    platform: str = "youtube_short"


@router.post("/{vid}/clips", status_code=201)
def create_clip(vid: str, body: ClipIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    v = get_or_404(db, Video, vid)
    if body.end <= body.start or body.end > (v.duration or 1e9) + 0.5:
        raise HTTPException(400, "invalid clip range")
    text = " ".join(s.text for s in v.segments if s.end >= body.start and s.start <= body.end)
    c = Clip(video_id=v.id, start=body.start, end=body.end, title=body.title or f"Manual clip {body.start:.0f}s", caption=body.caption, platform=body.platform, status="selected", transcript_text=text, why_it_works="Selected manually", score=0.0)
    db.add(c)
    db.commit()
    db.refresh(c)
    return d(c)


class ClipPatch(BaseModel):
    start: float | None = None
    end: float | None = None
    title: str | None = None
    caption: str | None = None
    platform: str | None = None
    status: str | None = None


@router.patch("/clips/{cid}")
def patch_clip(cid: str, body: ClipPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = get_or_404(db, Clip, cid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    if c.end <= c.start:
        raise HTTPException(400, "end must be after start")
    db.commit()
    return d(c)


class RenderIn(BaseModel):
    caption_style: str | None = None
    accent_color: str | None = None
    intro_text: str = ""
    progress_bar: bool = False
    watermark_text: str | None = None
    captions: bool = True
    face_tracking: bool | None = None
    size: str | None = None
    pad: float = 0.0


@router.post("/clips/{cid}/render")
def render(cid: str, body: RenderIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = get_or_404(db, Clip, cid)
    settings = {k: v for k, v in body.model_dump().items() if v is not None}
    c.status = "selected"
    db.commit()
    return d(enqueue(db, "render_clip", {"clip_id": cid, "settings": settings}))


@router.get("/clips/{cid}/file")
def clip_file(cid: str, db: Session = Depends(get_db)):
    c = get_or_404(db, Clip, cid)
    if not c.render_path or not Path(c.render_path).exists():
        raise HTTPException(404, "not rendered")
    return FileResponse(c.render_path, media_type="video/mp4", filename=Path(c.render_path).name)


@router.post("/clips/{cid}/to-content", status_code=201)
def clip_to_content(cid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = get_or_404(db, Clip, cid)
    item = ContentItem(title=c.title or f"Clip from {c.video.filename}", format=c.platform or "youtube_short", status="EDITING" if c.render_path else "RECORDED", script=c.transcript_text, source_video_id=c.video_id, clip_id=c.id, platform=c.platform, package={"caption": c.caption, "why_it_works": c.why_it_works, "render_path": c.render_path}, story_id=c.story_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return d(item)


@router.get("/{vid}/thumbnail")
def thumb(vid: str, t: float = 1.0, db: Session = Depends(get_db)):
    v = get_or_404(db, Video, vid)
    if not Path(v.path).exists():
        raise HTTPException(404, "missing file")
    out = get_settings().cache_path / f"thumb-{v.id}-{int(t)}.jpg"
    if not out.exists():
        try:
            svc.thumbnail(v.path, t, str(out))
        except RuntimeError as e:
            raise HTTPException(500, str(e)) from e
    return FileResponse(str(out), media_type="image/jpeg")


@router.get("/{vid}/segments/search")
def search_segments(vid: str, q: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(TranscriptSegment).where(TranscriptSegment.video_id == vid, TranscriptSegment.text.ilike(f"%{q}%")).order_by(TranscriptSegment.start)).scalars().all()
    return dl(rows)
