"""Faceless Content Studio API: faceless videos, carousels, memes, quality gate, exports."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..jobs.tasks import enqueue
from ..models import FACELESS_FORMATS, ContentItem, VideoProject
from ..providers.base import PrivacyViolation, ProviderError
from ..providers.tts.local import tts_status
from ..services import faceless, imagery, memes
from ..services import settings as settings_service
from ..services.render_video import render_scene_preview
from .common import d, get_or_404

router = APIRouter(prefix="/studio", tags=["studio"])


class SourceIn(BaseModel):
    story_id: str | None = None
    brief_id: str | None = None
    principle_id: str | None = None
    research_note_id: str | None = None
    video_id: str | None = None
    idea: str = ""


class FacelessIn(BaseModel):
    source: SourceIn
    kind: str = "faceless_video"  # faceless_video | carousel
    format: str | None = None
    target_seconds: int | None = None
    platform: str | None = None
    voice_mode: str | None = None
    title: str | None = None
    extra_instructions: str = ""
    background: bool = True


def _project(db: Session, p: VideoProject) -> dict[str, Any]:
    out = d(p)
    item = p.content_item
    out["title"] = item.title
    out["status"] = item.status
    out["fact_check_status"] = item.fact_check_status
    out["content_item"] = {"id": item.id, "title": item.title, "status": item.status, "format": item.format, "approved_at": item.approved_at.isoformat() if item.approved_at else None}
    out["total_seconds"] = faceless.total_duration(p.scenes or [])
    out["formats"] = {k: v["label"] for k, v in faceless.FORMAT_SPECS.items()}
    return out


@router.get("/formats")
def formats(db: Session = Depends(get_db)) -> dict[str, Any]:
    voice_cfg = settings_service.get(db, "voice", {}) or {}
    return {
        "formats": [{"id": k, "label": v["label"], "default_seconds": v["default_seconds"]} for k, v in faceless.FORMAT_SPECS.items()],
        "lengths": [15, 30, 45, 60],
        "variations": list(faceless.VARIATIONS.keys()),
        "meme_templates": memes.MEME_TEMPLATES,
        "tts": tts_status(voice_cfg.get("piper_model", "")),
    }


@router.post("/faceless", status_code=201)
def create_faceless(body: FacelessIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.format and body.format not in FACELESS_FORMATS:
        raise HTTPException(400, f"unknown format {body.format}")
    try:
        project = faceless.create_project(
            db, source=body.source.model_dump(), kind=body.kind, fmt=body.format,
            target_seconds=body.target_seconds, platform=body.platform, voice_mode=body.voice_mode, title=body.title,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if body.background:
        job = enqueue(db, "faceless_generate", {"project_id": project.id, "extra_instructions": body.extra_instructions})
        return {"project": _project(db, project), "job": d(job)}
    try:
        if project.kind == "carousel":
            faceless.generate_carousel_slides(db, project, extra_instructions=body.extra_instructions)
        else:
            faceless.generate_scenes(db, project, extra_instructions=body.extra_instructions)
    except ProviderError as e:
        raise HTTPException(503, str(e)) from e
    # Finding pictures means network calls, so it does not block the draft coming back — but
    # it does start immediately, so the slides fill in on their own rather than on request.
    job = enqueue(db, "faceless_imagery", {"project_id": project.id})
    return {"project": _project(db, project), "job": d(job)}


@router.get("/projects")
def list_projects(kind: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(VideoProject).order_by(VideoProject.updated_at.desc())
    if kind:
        q = q.where(VideoProject.kind == kind)
    return [_project(db, p) for p in db.execute(q.limit(100)).scalars()]


@router.get("/projects/{pid}")
def get_project(pid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _project(db, get_or_404(db, VideoProject, pid))


@router.get("/by-content/{cid}")
def by_content(cid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = db.execute(select(VideoProject).where(VideoProject.content_item_id == cid)).scalars().first()
    if p is None:
        raise HTTPException(404, "no studio project for this draft")
    return _project(db, p)


class ProjectPatch(BaseModel):
    scenes: list[dict[str, Any]] | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    voice_mode: str | None = None
    tts_voice: str | None = None
    music_path: str | None = None
    platform: str | None = None
    target_seconds: int | None = None
    brand_overrides: dict[str, Any] | None = None
    sources: list[dict[str, Any]] | None = None


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = get_or_404(db, VideoProject, pid)
    data = body.model_dump(exclude_none=True)
    scenes = data.pop("scenes", None)
    for k, v in data.items():
        setattr(p, k, v)
    if scenes is not None:
        try:
            faceless.update_scenes(db, p, scenes)
        except (ValueError, ProviderError) as e:
            raise HTTPException(400, str(e)) from e
    db.commit()
    return _project(db, p)


@router.post("/projects/{pid}/undo-scenes")
def undo_scenes(pid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = get_or_404(db, VideoProject, pid)
    if not p.previous_scenes:
        raise HTTPException(400, "nothing to undo")
    p.scenes, p.previous_scenes = p.previous_scenes, p.scenes
    p.render_status = "none"
    db.commit()
    return _project(db, p)


class VariationIn(BaseModel):
    variation: str


class ImageryIn(BaseModel):
    background: bool = True


@router.post("/projects/{pid}/imagery")
def add_pictures(pid: str, body: ImageryIn | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Give the scenes pictures: licensed photos, drawn marks, or a local illustration."""
    get_or_404(db, VideoProject, pid)
    return d(enqueue(db, "faceless_imagery", {"project_id": pid}))


@router.get("/projects/{pid}/scenes/{idx}/suggested-query")
def suggested_query(pid: str, idx: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """What this slide should be a picture *of*, before any picture has been chosen.

    The picker used to seed its search from the query recorded on an already-chosen picture,
    which meant a deck that had never run imagery had nothing to search for and showed an
    empty panel. The subject is knowable from the deck itself, so compute it on demand.
    """
    p = get_or_404(db, VideoProject, pid)
    scenes = p.scenes or []
    if not 0 <= idx < len(scenes):
        raise HTTPException(404, "scene not found")
    scene = scenes[idx]
    chosen = str((scene.get("visual") or {}).get("query") or "").strip()
    if chosen:
        return {"query": chosen, "source": "chosen"}
    cast = imagery.deck_subjects(db, p)
    guess, _subject, _thing = imagery._subject_query(scene, cast)
    if guess:
        return {"query": guess, "source": "subject"}
    # No name anywhere in the slide — fall back to what the deck as a whole is about, so the
    # panel still opens with something on-topic rather than nothing at all.
    top = cast[0].name if cast else ""
    return {"query": top or imagery.keywords(p.content_item.title or ""), "source": "deck"}


@router.get("/images/search")
def images_search(q: str, limit: int = 12, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Openly-licensed pictures only — everything returned may be republished with credit."""
    try:
        return {"results": imagery.search(db, q, limit=max(1, min(30, limit)))}
    except PrivacyViolation as e:
        raise HTTPException(403, str(e)) from e
    except ProviderError as e:
        raise HTTPException(502, str(e)) from e


class AttachIn(BaseModel):
    scene_index: int
    candidate: dict[str, Any]
    treatment: str = "band"


@router.post("/projects/{pid}/scenes/{idx}/image")
def attach_image(pid: str, idx: int, body: AttachIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Attach a chosen picture to one scene, with its licence recorded."""
    p = get_or_404(db, VideoProject, pid)
    scenes = [dict(s) for s in (p.scenes or [])]
    if not 0 <= idx < len(scenes):
        raise HTTPException(404, "scene not found")
    try:
        row = imagery.fetch(db, body.candidate, content_item_id=p.content_item_id)
    except PrivacyViolation as e:
        raise HTTPException(403, str(e)) from e
    except (ValueError, OSError) as e:
        raise HTTPException(400, str(e)) from e
    scenes[idx]["visual_type"] = "image"
    scenes[idx]["role"] = "image"
    scenes[idx]["visual"] = {
        **(scenes[idx].get("visual") or {}),
        "path": row.path, "image_id": row.id, "credit": imagery.credit_line(row),
        "pinned": True,  # chosen by hand — never replaced by a later Add pictures run
        "source_page": (row.params or {}).get("source_page", ""), "generated": bool(row.is_generated),
        "treatment": body.treatment if body.treatment in imagery.TREATMENTS else "band",
    }
    p.previous_scenes = p.scenes or []
    p.scenes = scenes
    p.render_status = "none"
    db.commit()
    return _project(db, p)


class AttachLibraryIn(BaseModel):
    image_id: str
    treatment: str = "band"


@router.post("/projects/{pid}/scenes/{idx}/image-from-library")
def attach_library_image(pid: str, idx: int, body: AttachLibraryIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Put a picture already in the library onto a scene. No download, no duplicate."""
    from ..models import Image

    p = get_or_404(db, VideoProject, pid)
    row = get_or_404(db, Image, body.image_id)
    scenes = [dict(s) for s in (p.scenes or [])]
    if not 0 <= idx < len(scenes):
        raise HTTPException(404, "scene not found")
    scenes[idx]["visual_type"] = "image"
    scenes[idx]["role"] = "image"
    scenes[idx]["visual"] = {
        **(scenes[idx].get("visual") or {}),
        "path": row.path, "image_id": row.id, "credit": imagery.credit_line(row),
        "source_page": (row.params or {}).get("source_page", ""), "generated": bool(row.is_generated),
        "pinned": True,
        "treatment": body.treatment if body.treatment in imagery.TREATMENTS else "band",
    }
    p.previous_scenes = p.scenes or []
    p.scenes = scenes
    p.render_status = "none"
    db.commit()
    return _project(db, p)


@router.post("/projects/{pid}/variation")
def variation(pid: str, body: VariationIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_or_404(db, VideoProject, pid)
    if body.variation not in faceless.VARIATIONS:
        raise HTTPException(400, f"unknown variation; options: {list(faceless.VARIATIONS)}")
    return d(enqueue(db, "faceless_variation", {"project_id": pid, "variation": body.variation}))


class SceneRegenIn(BaseModel):
    instruction: str = ""


@router.post("/projects/{pid}/scenes/{idx}/regenerate")
def regen_scene(pid: str, idx: int, body: SceneRegenIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = get_or_404(db, VideoProject, pid)
    try:
        faceless.regenerate_scene(db, p, idx, instruction=body.instruction)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except ProviderError as e:
        raise HTTPException(503, str(e)) from e
    return _project(db, p)


@router.get("/projects/{pid}/scenes/{idx}/preview")
def scene_preview(pid: str, idx: int, scale: float = 0.35, db: Session = Depends(get_db)):
    p = get_or_404(db, VideoProject, pid)
    try:
        path = render_scene_preview(db, p, idx, scale=max(0.1, min(1.0, scale)))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return FileResponse(str(path), media_type="image/png")


@router.post("/projects/{pid}/render")
def render(pid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = get_or_404(db, VideoProject, pid)
    if not p.scenes:
        raise HTTPException(400, "generate scenes first")
    p.render_status = "queued"
    db.commit()
    return d(enqueue(db, "faceless_render", {"project_id": pid}))


@router.get("/projects/{pid}/file")
def project_file(pid: str, db: Session = Depends(get_db)):
    p = get_or_404(db, VideoProject, pid)
    if p.render_status != "done" or not p.render_path or not Path(p.render_path).exists():
        raise HTTPException(404, "not rendered yet")
    path = Path(p.render_path)
    media = "video/mp4" if path.suffix == ".mp4" else "application/zip"
    return FileResponse(str(path), media_type=media, filename=path.name)


@router.get("/projects/{pid}/slides/{idx}/file")
def slide_file(pid: str, idx: int, db: Session = Depends(get_db)):
    p = get_or_404(db, VideoProject, pid)
    if p.kind != "carousel" or p.render_status != "done":
        raise HTTPException(404, "carousel not rendered")
    slide = Path(p.render_path).with_suffix("") / f"slide-{idx + 1:02d}.png"
    if not slide.exists():
        raise HTTPException(404, "slide not found")
    return FileResponse(str(slide), media_type="image/png")


@router.get("/projects/{pid}/quality")
def quality(pid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = get_or_404(db, VideoProject, pid)
    checks = faceless.quality_checks(db, p)
    return {"checks": checks, "passed": all(c["status"] != "fail" for c in checks)}


@router.get("/projects/{pid}/script")
def export_script(pid: str, db: Session = Depends(get_db)) -> dict[str, str]:
    p = get_or_404(db, VideoProject, pid)
    lines = [f"# {p.content_item.title}", ""]
    for i, s in enumerate(p.scenes or [], 1):
        lines.append(f"## Scene {i} ({s.get('duration', 0)}s, {s.get('visual_type')})")
        lines.append(f"TEXT: {s.get('on_screen_text', '')}")
        if s.get("subtext"):
            lines.append(f"SUB: {s['subtext']}")
        if s.get("narration"):
            lines.append(f"VO: {s['narration']}")
        if s.get("source"):
            lines.append(f"SOURCE: {s['source']}")
        lines.append("")
    if p.caption:
        lines += ["## Caption", p.caption, ""]
    if p.hashtags:
        lines.append("Hashtags: " + " ".join(f"#{h}" for h in p.hashtags))
    if p.sources:
        lines += ["", "## Sources"] + [f"- {s.get('label')}: {s.get('url')}" for s in p.sources]
    return {"markdown": "\n".join(lines)}


# ---------------------------------------------------------------------------
# Memes
# ---------------------------------------------------------------------------
class MemeConceptsIn(BaseModel):
    source: SourceIn | None = None
    idea: str = ""
    humor: str = ""


@router.post("/memes/concepts")
def meme_concepts(body: MemeConceptsIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        concepts = memes.generate_concepts(db, source=body.source.model_dump() if body.source else None, idea=body.idea, humor=body.humor)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except ProviderError as e:
        raise HTTPException(503, str(e)) from e
    return {"concepts": concepts}


class MemeRenderIn(BaseModel):
    template: str
    top_text: str = ""
    bottom_text: str = ""
    title: str = ""
    caption: str = ""
    base_image: str | None = None
    content_item_id: str | None = None
    save_as_draft: bool = True
    story_id: str | None = None
    principle_ids: list[str] = []


@router.post("/memes/render", status_code=201)
def meme_render(body: MemeRenderIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.template not in memes.MEME_TEMPLATES:
        raise HTTPException(400, f"unknown template; options: {memes.MEME_TEMPLATES}")
    cid = body.content_item_id
    if body.save_as_draft and not cid:
        item = ContentItem(title=(body.title or body.top_text or "Meme")[:400], format="meme", status="EDITING", platform="meme", story_id=body.story_id, principle_ids=body.principle_ids, script=f"{body.top_text}\n{body.bottom_text}\n\nCaption: {body.caption}")
        db.add(item)
        db.flush()
        cid = item.id
    img = memes.render_meme(db, template=body.template, top_text=body.top_text, bottom_text=body.bottom_text, title=body.title, base_image=body.base_image, content_item_id=cid, params={"caption": body.caption})
    out = d(img)
    out["content_item_id"] = cid
    out["file_url"] = f"/api/images/{img.id}/file"
    return out
