"""Settings, privacy, local AI status, jobs, search, images, dashboard."""
from __future__ import annotations

import platform
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, has_pgvector
from ..jobs.tasks import enqueue, retry_job
from ..models import TASK_CATEGORIES, Clip, ContentItem, Image, Job, LocalModel, PositionBrief, Principle, Story, ThinkSession, Video
from ..providers import registry
from ..providers.base import ProviderError
from ..providers.transcription.detect import is_apple_silicon, recommended_install
from ..services import images as image_svc
from ..services import settings as settings_service
from ..services.privacy import NetworkPolicy
from ..services.search import ENTITY_MODELS, search
from .common import d, dl, get_or_404

router = APIRouter(tags=["system"])


# ---- settings -------------------------------------------------------------
@router.get("/settings")
def get_all_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    cfg = get_settings()
    out = settings_service.all_settings(db)
    out["privacy"] = NetworkPolicy.load(db).to_dict()
    out["env"] = {
        "database": "postgresql" if not cfg.is_sqlite else "sqlite",
        "database_url_masked": cfg.resolved_database_url.split("@")[-1] if "@" in cfg.resolved_database_url else cfg.resolved_database_url,
        "pgvector": has_pgvector() if not cfg.is_sqlite else False,
        "data_dir": str(cfg.data_path),
        "ffmpeg": registry.ffmpeg_available(),
        "ollama_url": cfg.ollama_url,
        "openai_compat_urls": cfg.openai_compat_url_list,
        "anthropic_key_present": bool(cfg.anthropic_api_key),
        "openai_key_present": bool(cfg.openai_api_key),
        "brave_key_present": bool(cfg.brave_api_key),
        "tavily_key_present": bool(cfg.tavily_api_key),
        "newsapi_key_present": bool(cfg.newsapi_key),
        "daily_ingest": f"{cfg.daily_ingest_hour:02d}:{cfg.daily_ingest_minute:02d}",
        "platform": f"{platform.system()} {platform.machine()}",
        "apple_silicon": is_apple_silicon(),
        "transcription_recommendation": recommended_install(),
    }
    return out


class SettingsPatch(BaseModel):
    key: str
    value: dict[str, Any]


@router.patch("/settings")
def patch_settings(body: SettingsPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.key in ("privacy",):
        raise HTTPException(400, "use /settings/privacy")
    return {body.key: settings_service.update(db, body.key, body.value)}


class PrivacyIn(BaseModel):
    local_ai_only: bool | None = None
    allow_internet_research: bool | None = None
    allow_cloud_ai: bool | None = None
    confirm_cloud: bool = False


@router.get("/settings/privacy")
def get_privacy(db: Session = Depends(get_db)) -> dict[str, Any]:
    return NetworkPolicy.load(db).to_dict()


@router.patch("/settings/privacy")
def patch_privacy(body: PrivacyIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    pol = NetworkPolicy.load(db)
    if body.allow_cloud_ai is True and not body.confirm_cloud:
        raise HTTPException(400, "Enabling cloud AI requires explicit confirmation (confirm_cloud=true).")
    for k in ("local_ai_only", "allow_internet_research", "allow_cloud_ai"):
        v = getattr(body, k)
        if v is not None:
            setattr(pol, k, v)
    pol.save(db)
    return pol.to_dict()


# ---- local AI -------------------------------------------------------------
@router.get("/local-ai")
def local_ai(db: Session = Depends(get_db)) -> dict[str, Any]:
    models = db.execute(select(LocalModel).order_by(LocalModel.runtime, LocalModel.priority, LocalModel.name)).scalars().all()
    runtimes = settings_service.get(db, "detected_runtimes", []) or []
    return {
        "runtimes": runtimes,
        "models": dl(models),
        "assignments": registry.recommend_assignments(db),
        "task_categories": TASK_CATEGORIES,
        "ffmpeg": registry.ffmpeg_available(),
        "image_provider": image_svc.image_provider_status(),
        "last_detection": settings_service.get(db, "last_detection", None),
    }


@router.post("/local-ai/refresh")
def refresh_models(db: Session = Depends(get_db)) -> dict[str, Any]:
    res = registry.detect_and_register(db)
    settings_service.set(db, "detected_runtimes", res["runtimes"])
    settings_service.set(db, "last_detection", datetime.now(timezone.utc).isoformat())
    return res


@router.post("/local-ai/models/{mid}/test")
def test_model(mid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_or_404(db, LocalModel, mid)
    try:
        return registry.test_model(db, mid)
    except ProviderError as e:
        return {"ok": False, "detail": str(e)}


class ModelPatch(BaseModel):
    tasks: list[str] | None = None
    enabled: bool | None = None
    priority: int | None = None
    fallback_model_id: str | None = None
    context_window: int | None = None


@router.patch("/local-ai/models/{mid}")
def patch_model(mid: str, body: ModelPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    m = get_or_404(db, LocalModel, mid)
    data = body.model_dump(exclude_none=True)
    if "tasks" in data:
        bad = [t for t in data["tasks"] if t not in TASK_CATEGORIES]
        if bad:
            raise HTTPException(400, f"unknown task categories {bad}")
    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    return d(m)


class ModelIn(BaseModel):
    name: str
    runtime: str
    endpoint: str = ""
    tasks: list[str] = ["FAST"]
    priority: int = 100
    context_window: int | None = None
    locality: str = "local"


@router.post("/local-ai/models", status_code=201)
def add_model(body: ModelIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Manually register a model/endpoint (e.g. a llama.cpp server on a custom port)."""
    m = LocalModel(**body.model_dump(), detected=True, enabled=True)
    db.add(m)
    db.commit()
    return d(m)


@router.delete("/local-ai/models/{mid}", status_code=204)
def del_model(mid: str, db: Session = Depends(get_db)) -> None:
    m = get_or_404(db, LocalModel, mid)
    db.delete(m)
    db.commit()


# ---- jobs -----------------------------------------------------------------
@router.get("/jobs")
def list_jobs(status: str | None = None, limit: int = 50, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(Job)
    if status:
        q = q.where(Job.status == status)
    return dl(db.execute(q.order_by(Job.created_at.desc()).limit(limit)).scalars())


@router.get("/jobs/{jid}")
def get_job(jid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return d(get_or_404(db, Job, jid))


@router.post("/jobs/{jid}/retry")
def retry(jid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    j = get_or_404(db, Job, jid)
    return d(retry_job(db, j))


class JobIn(BaseModel):
    kind: str
    payload: dict[str, Any] = {}


@router.post("/jobs", status_code=201)
def create_job_endpoint(body: JobIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return d(enqueue(db, body.kind, body.payload))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e)) from e


# ---- search ---------------------------------------------------------------
@router.get("/search")
def global_search(q: str, types: str | None = None, limit: int = 20, db: Session = Depends(get_db)) -> dict[str, Any]:
    tlist = [t for t in (types or "").split(",") if t in ENTITY_MODELS] or None
    hits = search(db, q, types=tlist, limit=limit)
    return {"query": q, "hits": [h.__dict__ for h in hits]}


# ---- images ---------------------------------------------------------------
class ImageIn(BaseModel):
    kind: str
    params: dict[str, Any]
    content_item_id: str | None = None
    title: str = ""


@router.get("/images")
def list_images(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return dl(db.execute(select(Image).order_by(Image.created_at.desc())).scalars())


@router.post("/images", status_code=201)
def create_image(body: ImageIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return d(image_svc.create_image(db, kind=body.kind, params=body.params, content_item_id=body.content_item_id, title=body.title))
    except ProviderError as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/images/{iid}/file")
def image_file(iid: str, db: Session = Depends(get_db)):
    im = get_or_404(db, Image, iid)
    return FileResponse(im.path, media_type="image/png")


class ImageApprove(BaseModel):
    approved: bool


@router.post("/images/{iid}/approve")
def approve_image(iid: str, body: ImageApprove, db: Session = Depends(get_db)) -> dict[str, Any]:
    im = get_or_404(db, Image, iid)
    im.approved = body.approved
    db.commit()
    return d(im)


@router.delete("/images/{iid}", status_code=204)
def del_image(iid: str, db: Session = Depends(get_db)) -> None:
    im = get_or_404(db, Image, iid)
    db.delete(im)
    db.commit()


# ---- dashboard ------------------------------------------------------------
@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=3)
    stories = db.execute(select(Story).where(Story.last_updated >= since, Story.status != "ignored").order_by(Story.relevance_score.desc(), Story.last_updated.desc()).limit(40)).scalars().all()

    def s_row(s: Story) -> dict[str, Any]:
        return {
            "id": s.id, "title": s.title, "summary": s.summary, "why_it_matters": s.why_it_matters, "relevance_score": s.relevance_score,
            "topics": s.topics, "status": s.status, "last_updated": s.last_updated.isoformat(), "article_count": len([a for a in s.articles if not a.duplicate_of_id]),
            "principles": [{"id": l.principle_id, "title": l.principle.title, "relation": l.relation, "strength": l.strength} for l in sorted(s.principle_links, key=lambda l: -l.strength)[:4]],
            "arguments": s.arguments[:4], "primary_sources": s.primary_sources[:3], "content_potential": s.content_potential[:2], "recommended_format": s.recommended_format, "dashboard_action": s.dashboard_action, "analysis_source": s.analysis_source,
        }

    top = [s_row(s) for s in stories[:10]]
    think_about = [s_row(s) for s in sorted([s for s in stories if any(l.relation == "challenges" for l in s.principle_links) or s.relevance_score >= 0.6], key=lambda s: -s.relevance_score)[:3]]
    create = [s_row(s) for s in sorted([s for s in stories if s.content_potential], key=lambda s: -max((c.get("score", 0) or 0) for c in s.content_potential if isinstance(c, dict)))[:4]]
    sessions = db.execute(select(ThinkSession).where(ThinkSession.status == "active").order_by(ThinkSession.updated_at.desc()).limit(5)).scalars().all()
    briefs = db.execute(select(PositionBrief).where(PositionBrief.status == "draft").order_by(PositionBrief.created_at.desc()).limit(5)).scalars().all()
    content = db.execute(select(ContentItem).where(ContentItem.status.in_(["SCRIPTING", "EDITING", "RESEARCHING", "POSITION_DEVELOPED"])).order_by(ContentItem.updated_at.desc()).limit(6)).scalars().all()
    clips = db.execute(select(Clip).where(Clip.status.in_(["suggested", "selected", "rendered"])).order_by(Clip.created_at.desc(), Clip.score.desc()).limit(6)).scalars().all()
    return {
        "generated_at": now.isoformat(),
        "counts": {"stories_3d": len(stories), "principles": db.query(Principle).filter(Principle.status != "retired").count(), "videos": db.query(Video).count(), "content": db.query(ContentItem).count()},
        "last_ingest": settings_service.get(db, "last_ingest", {}) or {},
        "today": top,
        "think_about": think_about,
        "create": create,
        "continue": {
            "think_sessions": [{"id": t.id, "title": t.title, "updated_at": t.updated_at.isoformat(), "exchanges": sum(1 for m in t.messages or [] if m.get("role") == "user")} for t in sessions],
            "briefs": [{"id": b.id, "issue": b.issue, "confidence": b.confidence} for b in briefs],
            "content": [{"id": c.id, "title": c.title, "format": c.format, "status": c.status} for c in content],
        },
        "recent_clips": [{"id": c.id, "title": c.title, "video_id": c.video_id, "video": c.video.filename, "start": c.start, "end": c.end, "score": c.score, "status": c.status, "platform": c.platform} for c in clips],
        "privacy": NetworkPolicy.load(db).to_dict(),
    }
