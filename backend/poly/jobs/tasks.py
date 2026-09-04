"""Background tasks. Every task is tracked by a `Job` row so the UI can show real progress,
failures and retries. Nothing here falls back to cloud AI.
"""
from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from huey import crontab

from ..config import get_settings
from ..db import session_scope
from ..models import Job
from ..providers.base import ProviderError
from .huey_app import huey

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def create_job(db, kind: str, payload: dict[str, Any] | None = None) -> Job:
    job = Job(kind=kind, payload=payload or {}, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _run_tracked(job_id: str, fn: Callable[[Any, Job, Callable[[float, str], None]], dict[str, Any]]) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = _now()
        job.attempts = (job.attempts or 0) + 1
        db.commit()

        def progress(frac: float, msg: str = "") -> None:
            job.progress = float(max(0.0, min(1.0, frac)))
            job.result = {**(job.result or {}), "message": msg}
            db.commit()

        try:
            result = fn(db, job, progress) or {}
            job.result = {**(job.result or {}), **result}
            job.status = "succeeded"
            job.progress = 1.0
            job.error = None
        except ProviderError as e:
            db.rollback()
            job = db.get(Job, job_id)
            job.status = "failed"
            job.error = str(e)
            job.retryable = e.retryable
            job.result = {**(job.result or {}), "hint": "Local model/runtime failed. Retry, pick another local model in Settings → Local AI, or explicitly allow cloud AI."}
        except Exception as e:  # noqa: BLE001
            db.rollback()
            job = db.get(Job, job_id)
            job.status = "failed"
            job.error = f"{e}\n{traceback.format_exc()[-1500:]}"
        job.finished_at = _now()
        db.commit()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
@huey.task()
def ingest_task(job_id: str, feed_ids: list[str] | None = None) -> None:
    from ..services.ingest import run_ingest

    def run(db, job, progress):
        return run_ingest(db, feed_ids=feed_ids, progress=progress)

    _run_tracked(job_id, run)


@huey.task()
def analyze_story_task(job_id: str, story_id: str) -> None:
    from ..models import Story
    from ..services.analysis import analyze_story

    def run(db, job, progress):
        story = db.get(Story, story_id)
        if story is None:
            raise ValueError("story not found")
        analyze_story(db, story)
        return {"story_id": story_id, "relevance": story.relevance_score, "source": story.analysis_source}

    _run_tracked(job_id, run)


@huey.task()
def embed_task(job_id: str, entity_type: str, entity_id: str) -> None:
    from ..services.search import ENTITY_MODELS, embed_entity

    def run(db, job, progress):
        obj = db.get(ENTITY_MODELS[entity_type], entity_id)
        if obj is None:
            raise ValueError("entity not found")
        return {"chunks": embed_entity(db, entity_type, obj)}

    _run_tracked(job_id, run)


@huey.task()
def reembed_task(job_id: str) -> None:
    from ..services.search import reembed_stale

    _run_tracked(job_id, lambda db, job, progress: {"reembedded": reembed_stale(db)})


@huey.task()
def scan_folder_task(job_id: str, folder_id: str) -> None:
    from ..models import VideoFolder
    from ..services.media import scan_folder

    def run(db, job, progress):
        folder = db.get(VideoFolder, folder_id)
        if folder is None:
            raise ValueError("folder not found")
        return scan_folder(db, folder, progress=progress)

    _run_tracked(job_id, run)


@huey.task()
def transcribe_task(job_id: str, video_id: str) -> None:
    from ..models import Video
    from ..services.media import transcribe_video

    def run(db, job, progress):
        video = db.get(Video, video_id)
        if video is None:
            raise ValueError("video not found")
        transcribe_video(db, video, progress=progress)
        return {"video_id": video_id, "segments": len(video.segments), "provider": video.transcript_provider}

    _run_tracked(job_id, run)


@huey.task()
def discover_clips_task(job_id: str, video_id: str) -> None:
    from ..models import Video
    from ..services.media import discover_clips

    def run(db, job, progress):
        video = db.get(Video, video_id)
        if video is None:
            raise ValueError("video not found")
        clips = discover_clips(db, video)
        return {"video_id": video_id, "clips": len(clips)}

    _run_tracked(job_id, run)


@huey.task()
def render_clip_task(job_id: str, clip_id: str, settings: dict[str, Any] | None = None) -> None:
    from ..models import Clip
    from ..services.media import render_clip

    def run(db, job, progress):
        clip = db.get(Clip, clip_id)
        if clip is None:
            raise ValueError("clip not found")
        render_clip(db, clip, settings=settings, progress=progress)
        return {"clip_id": clip_id, "render_path": clip.render_path}

    _run_tracked(job_id, run)


@huey.task()
def generate_content_task(job_id: str, params: dict[str, Any]) -> None:
    from ..services.content import generate

    def run(db, job, progress):
        item = generate(db, **params)
        return {"content_item_id": item.id, "title": item.title}

    _run_tracked(job_id, run)


@huey.task()
def social_bundle_task(job_id: str, content_item_id: str) -> None:
    from ..models import ContentItem
    from ..services.content import generate_social_bundle

    def run(db, job, progress):
        item = db.get(ContentItem, content_item_id)
        if item is None:
            raise ValueError("content item not found")
        return generate_social_bundle(db, item)

    _run_tracked(job_id, run)


@huey.task()
def fact_check_task(job_id: str, content_item_id: str) -> None:
    from ..models import ContentItem
    from ..services.factcheck import run_fact_check

    def run(db, job, progress):
        item = db.get(ContentItem, content_item_id)
        if item is None:
            raise ValueError("content item not found")
        claims = run_fact_check(db, item)
        return {"claims": len(claims), "unresolved": sum(1 for c in claims if not c.resolved), "status": item.fact_check_status}

    _run_tracked(job_id, run)


@huey.task()
def faceless_generate_task(job_id: str, project_id: str, extra_instructions: str = "") -> None:
    from ..models import VideoProject
    from ..services.faceless import generate_carousel_slides, generate_scenes
    from ..services.imagery import add_imagery

    def run(db, job, progress):
        project = db.get(VideoProject, project_id)
        if project is None:
            raise ValueError("project not found")
        progress(0.1, "Writing scenes")
        if project.kind == "carousel":
            generate_carousel_slides(db, project, extra_instructions=extra_instructions)
        else:
            generate_scenes(db, project, extra_instructions=extra_instructions)
        # Pictures are part of a finished draft, not an extra step. A deck that arrives as
        # seven text cards reads as broken, and the picture panel has nothing to work from
        # until something has been picked — so find them now rather than waiting to be asked.
        progress(0.6, "Finding pictures")
        try:
            add_imagery(db, project, progress=lambda f, m="": progress(0.6 + 0.4 * f, m))
        except Exception as e:  # a picture problem must never lose the written draft
            log.warning("imagery skipped for %s: %s", project_id, e)
        return {"project_id": project_id, "scenes": len(project.scenes or []), "content_item_id": project.content_item_id}

    _run_tracked(job_id, run)


@huey.task()
def faceless_render_task(job_id: str, project_id: str) -> None:
    from ..models import VideoProject
    from ..services.render_video import render_project

    def run(db, job, progress):
        project = db.get(VideoProject, project_id)
        if project is None:
            raise ValueError("project not found")
        render_project(db, project, progress=progress)
        return {"project_id": project_id, "render_path": project.render_path}

    _run_tracked(job_id, run)


@huey.task()
def faceless_variation_task(job_id: str, project_id: str, variation: str) -> None:
    from ..models import VideoProject
    from ..services.faceless import apply_variation

    def run(db, job, progress):
        project = db.get(VideoProject, project_id)
        if project is None:
            raise ValueError("project not found")
        progress(0.1, f"Rewriting: {variation.replace('_', ' ')}")
        apply_variation(db, project, variation)
        return {"project_id": project_id, "variation": variation}

    _run_tracked(job_id, run)


@huey.task()
def faceless_imagery_task(job_id: str, project_id: str) -> None:
    from ..models import VideoProject
    from ..services.imagery import add_imagery

    def run(db, job, progress):
        project = db.get(VideoProject, project_id)
        if project is None:
            raise ValueError("project not found")
        progress(0.05, "Finding pictures")
        add_imagery(db, project, progress=progress)
        with_pictures = sum(1 for s in project.scenes or [] if (s.get("visual") or {}).get("path") or s.get("visual_type") == "symbol")
        return {"project_id": project_id, "scenes_with_pictures": with_pictures}

    _run_tracked(job_id, run)


@huey.task()
def detect_models_task(job_id: str) -> None:
    from ..providers.registry import detect_and_register

    _run_tracked(job_id, lambda db, job, progress: detect_and_register(db))


# ---------------------------------------------------------------------------
# Periodic
# ---------------------------------------------------------------------------
_cfg = get_settings()


@huey.periodic_task(crontab(minute=str(_cfg.daily_ingest_minute), hour=str(_cfg.daily_ingest_hour)))
def daily_ingest() -> None:
    with session_scope() as db:
        job = create_job(db, "ingest", {"trigger": "daily"})
        jid = job.id
    ingest_task(jid)


@huey.periodic_task(crontab(minute="15", hour="*/6"))
def periodic_reembed() -> None:
    with session_scope() as db:
        job = create_job(db, "reembed", {"trigger": "periodic"})
        jid = job.id
    reembed_task(jid)


# ---------------------------------------------------------------------------
# Enqueue helpers (used by the API)
# ---------------------------------------------------------------------------
def enqueue(db, kind: str, payload: dict[str, Any] | None = None) -> Job:
    job = create_job(db, kind, payload)
    payload = payload or {}
    table = {
        "ingest": lambda: ingest_task(job.id, payload.get("feed_ids")),
        "analyze_story": lambda: analyze_story_task(job.id, payload["story_id"]),
        "embed": lambda: embed_task(job.id, payload["entity_type"], payload["entity_id"]),
        "reembed": lambda: reembed_task(job.id),
        "scan_folder": lambda: scan_folder_task(job.id, payload["folder_id"]),
        "transcribe": lambda: transcribe_task(job.id, payload["video_id"]),
        "discover_clips": lambda: discover_clips_task(job.id, payload["video_id"]),
        "render_clip": lambda: render_clip_task(job.id, payload["clip_id"], payload.get("settings")),
        "generate_content": lambda: generate_content_task(job.id, payload["params"]),
        "social_bundle": lambda: social_bundle_task(job.id, payload["content_item_id"]),
        "fact_check": lambda: fact_check_task(job.id, payload["content_item_id"]),
        "detect_models": lambda: detect_models_task(job.id),
        "faceless_generate": lambda: faceless_generate_task(job.id, payload["project_id"], payload.get("extra_instructions", "")),
        "faceless_render": lambda: faceless_render_task(job.id, payload["project_id"]),
        "faceless_variation": lambda: faceless_variation_task(job.id, payload["project_id"], payload["variation"]),
        "faceless_imagery": lambda: faceless_imagery_task(job.id, payload["project_id"]),
    }
    if kind not in table:
        raise ValueError(f"unknown job kind {kind}")
    table[kind]()
    db.refresh(job)
    return job


def retry_job(db, job: Job) -> Job:
    if job.status != "failed":
        return job
    return enqueue(db, job.kind, dict(job.payload or {}))
