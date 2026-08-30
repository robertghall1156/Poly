"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import book, content, principles, stories, studio, system, think, videos
from .config import get_settings
from .db import init_db, session_scope

log = logging.getLogger("poly")


def startup_tasks() -> dict:
    """Idempotent first-run setup: schema, principles seed, feeds, runtime detection."""
    from .providers.registry import detect_and_register
    from .services import settings as settings_service
    from .services.ingest import ensure_default_feeds
    from .services.principles import import_markdown, list_principles
    from .services.search import embed_entity

    init_db()
    summary: dict = {}
    with session_scope() as db:
        res = import_markdown(db, only_if_empty=True)
        summary["principles"] = res
        if res.get("created"):
            for p in list_principles(db):
                embed_entity(db, "principle", p)
        summary["feeds_added"] = ensure_default_feeds(db)
        try:
            det = detect_and_register(db)
            settings_service.set(db, "detected_runtimes", det["runtimes"])
            settings_service.set(db, "last_detection", datetime.now(UTC).isoformat())
            summary["runtimes"] = det["runtimes"]
            summary["assignments"] = det["assignments"]
        except Exception as e:  # detection must never block startup
            log.warning("runtime detection failed: %s", e)
            summary["runtimes_error"] = str(e)
    return summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    summary = startup_tasks()
    running = [r["runtime"] for r in summary.get("runtimes", []) if r.get("running")]
    log.info("Poly %s started. DB=%s local runtimes=%s", __version__, "sqlite" if get_settings().is_sqlite else "postgres", running or "none detected")
    app.state.startup = summary
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Poly", version=__version__, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])
    for r in (principles.router, stories.router, think.router, content.router, videos.router, book.router, studio.router, system.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": __version__, "startup": getattr(app.state, "startup", {})}

    return app


app = create_app()
