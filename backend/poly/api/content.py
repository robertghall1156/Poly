from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from dateutil import parser as dateparser
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..jobs.tasks import enqueue
from ..models import CONTENT_FORMATS, CONTENT_STATUSES, ContentItem, ContentMetric, FactCheckClaim
from ..services import content as svc
from ..services import factcheck
from ..services.search import embed_entity
from .common import d, dl, get_or_404

router = APIRouter(prefix="/content", tags=["content"])


def _item(db: Session, c: ContentItem) -> dict[str, Any]:
    out = d(c)
    out["children"] = [{"id": k.id, "title": k.title, "format": k.format, "status": k.status} for k in c.children]
    out["fact_check_claims"] = dl(c.fact_check_claims)
    out["metrics"] = dl(c.metrics)
    out["lineage"] = svc.lineage(db, c)
    return out


@router.get("/formats")
def formats() -> dict[str, list[str]]:
    return {"formats": CONTENT_FORMATS, "statuses": CONTENT_STATUSES}


@router.get("")
def list_items(status: str | None = None, format: str | None = None, story_id: str | None = None, roots_only: bool = False, limit: int = 300, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(ContentItem)
    if status:
        q = q.where(ContentItem.status == status)
    if format:
        q = q.where(ContentItem.format == format)
    if story_id:
        q = q.where(ContentItem.story_id == story_id)
    if roots_only:
        q = q.where(ContentItem.parent_id.is_(None))
    rows = db.execute(q.order_by(ContentItem.updated_at.desc()).limit(limit)).scalars().all()
    out = []
    for c in rows:
        row = d(c)
        row.pop("package", None)
        row["script_preview"] = (c.script or "")[:200]
        row["child_count"] = len(c.children)
        row["unresolved_claims"] = sum(1 for f in c.fact_check_claims if not f.resolved)
        out.append(row)
    return out


class ItemIn(BaseModel):
    title: str
    format: str
    status: str = "IDEA"
    story_id: str | None = None
    principle_ids: list[str] = []
    position_brief_id: str | None = None
    script: str = ""
    parent_id: str | None = None
    platform: str = ""
    publish_date: str | None = None
    url: str = ""
    source_video_id: str | None = None
    clip_id: str | None = None


@router.post("", status_code=201)
def create_item(body: ItemIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    data = body.model_dump()
    if data.get("publish_date"):
        data["publish_date"] = dateparser.parse(data["publish_date"])
    try:
        item = svc.create_item(db, data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return _item(db, item)


@router.get("/{cid}")
def get_item(cid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _item(db, get_or_404(db, ContentItem, cid))


class ItemPatch(BaseModel):
    title: str | None = None
    script: str | None = None
    package: dict[str, Any] | None = None
    platform: str | None = None
    publish_date: str | None = None
    url: str | None = None
    principle_ids: list[str] | None = None
    substantive_value: float | None = None
    story_id: str | None = None


@router.patch("/{cid}")
def patch_item(cid: str, body: ItemPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = get_or_404(db, ContentItem, cid)
    data = body.model_dump(exclude_none=True)
    if "publish_date" in data:
        data["publish_date"] = dateparser.parse(data["publish_date"]) if data["publish_date"] else None
    if "script" in data and data["script"] != c.script:
        c.fact_check_status = "not_run" if c.fact_check_status == "fact_checked" else c.fact_check_status
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    embed_entity(db, "content_item", c)
    return _item(db, c)


class StatusIn(BaseModel):
    status: str
    override_reason: str = ""


@router.post("/{cid}/status")
def set_status(cid: str, body: StatusIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = get_or_404(db, ContentItem, cid)
    try:
        svc.set_status(db, c, body.status, override_reason=body.override_reason)
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return _item(db, c)


@router.delete("/{cid}", status_code=204)
def delete_item(cid: str, db: Session = Depends(get_db)) -> None:
    c = get_or_404(db, ContentItem, cid)
    for k in c.children:
        k.parent_id = None
    db.delete(c)
    db.commit()


class GenerateIn(BaseModel):
    format: str
    story_id: str | None = None
    brief_id: str | None = None
    principle_ids: list[str] = []
    parent_id: str | None = None
    title: str | None = None
    extra_instructions: str = ""
    background: bool = True


@router.post("/generate")
def generate(body: GenerateIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    params = {"fmt": body.format, "story_id": body.story_id, "brief_id": body.brief_id, "principle_ids": body.principle_ids, "parent_id": body.parent_id, "title": body.title, "extra_instructions": body.extra_instructions}
    if body.background:
        return {"job": d(enqueue(db, "generate_content", {"params": params}))}
    from ..providers.base import ProviderError

    try:
        item = svc.generate(db, **params)
    except ProviderError as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"item": _item(db, item)}


@router.post("/{cid}/social")
def social(cid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_or_404(db, ContentItem, cid)
    return d(enqueue(db, "social_bundle", {"content_item_id": cid}))


@router.get("/{cid}/tree")
def tree(cid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return svc.content_tree(db, get_or_404(db, ContentItem, cid))


@router.post("/{cid}/fact-check")
def fact_check(cid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    get_or_404(db, ContentItem, cid)
    return d(enqueue(db, "fact_check", {"content_item_id": cid}))


class ClaimResolve(BaseModel):
    status: str
    sources: list[str] | None = None
    notes: str = ""


@router.post("/{cid}/claims/{fid}")
def resolve_claim(cid: str, fid: str, body: ClaimResolve, db: Session = Depends(get_db)) -> dict[str, Any]:
    fc = get_or_404(db, FactCheckClaim, fid)
    try:
        factcheck.resolve_claim(db, fc, status=body.status, sources=body.sources, notes=body.notes)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return _item(db, fc.content_item)


# ---- calendar ----
@router.get("/calendar/board")
def board(db: Session = Depends(get_db)) -> dict[str, list[dict[str, Any]]]:
    rows = db.execute(select(ContentItem).order_by(ContentItem.publish_date.asc().nulls_last(), ContentItem.updated_at.desc())).scalars().all()
    out: dict[str, list[dict[str, Any]]] = {s: [] for s in CONTENT_STATUSES}
    for c in rows:
        out[c.status].append({"id": c.id, "title": c.title, "format": c.format, "platform": c.platform, "publish_date": c.publish_date.isoformat() if c.publish_date else None, "parent_id": c.parent_id, "fact_check_status": c.fact_check_status, "url": c.url})
    return out


# ---- metrics / analytics ----
class MetricIn(BaseModel):
    platform: str = ""
    recorded_at: str | None = None
    views: int = 0
    watch_time_seconds: float = 0
    retention_pct: float | None = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    subscribers_gained: int = 0
    completion_pct: float | None = None


@router.post("/{cid}/metrics", status_code=201)
def add_metric(cid: str, body: MetricIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = get_or_404(db, ContentItem, cid)
    data = body.model_dump()
    data["recorded_at"] = dateparser.parse(data["recorded_at"]) if data.get("recorded_at") else datetime.now(UTC)
    m = ContentMetric(content_item_id=c.id, source="manual", **data)
    db.add(m)
    db.commit()
    return d(m)


@router.post("/metrics/import-csv")
async def import_csv(file: UploadFile, db: Session = Depends(get_db)) -> dict[str, Any]:
    """CSV columns: content_item_id (or title), platform, recorded_at, views, watch_time_seconds, retention_pct, likes, comments, shares, subscribers_gained, completion_pct"""
    text = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    n, skipped = 0, 0
    for row in reader:
        item = None
        if row.get("content_item_id"):
            item = db.get(ContentItem, row["content_item_id"])
        if item is None and row.get("title"):
            item = db.execute(select(ContentItem).where(ContentItem.title == row["title"])).scalars().first()
        if item is None:
            skipped += 1
            continue

        def num(k, cast=int, default=0, row=row):
            v = row.get(k)
            try:
                return cast(v) if v not in (None, "") else default
            except ValueError:
                return default

        m = ContentMetric(content_item_id=item.id, platform=row.get("platform", ""), recorded_at=dateparser.parse(row["recorded_at"]) if row.get("recorded_at") else datetime.now(UTC), views=num("views"), watch_time_seconds=num("watch_time_seconds", float, 0.0), retention_pct=num("retention_pct", float, None), likes=num("likes"), comments=num("comments"), shares=num("shares"), subscribers_gained=num("subscribers_gained"), completion_pct=num("completion_pct", float, None), source="csv")
        db.add(m)
        n += 1
    db.commit()
    return {"imported": n, "skipped": skipped}


@router.get("/analytics/overview")
def analytics(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute(select(ContentItem).where(ContentItem.status == "PUBLISHED")).scalars().all()
    items = []
    for c in rows:
        if not c.metrics:
            continue
        latest = max(c.metrics, key=lambda m: m.recorded_at)
        engagement = latest.views + 5 * latest.likes + 10 * latest.comments + 15 * latest.shares
        verified = sum(1 for f in c.fact_check_claims if f.status == "VERIFIED")
        total_claims = len(c.fact_check_claims)
        substance = c.substantive_value if c.substantive_value is not None else (2.5 + 2.5 * (verified / total_claims) if total_claims else 2.5)
        items.append({"id": c.id, "title": c.title, "format": c.format, "platform": c.platform, "publish_date": c.publish_date.isoformat() if c.publish_date else None, "views": latest.views, "likes": latest.likes, "comments": latest.comments, "shares": latest.shares, "watch_time_seconds": latest.watch_time_seconds, "retention_pct": latest.retention_pct, "completion_pct": latest.completion_pct, "engagement": engagement, "substantive_value": round(float(substance), 2), "verified_claims": verified, "total_claims": total_claims})
    if items:
        med = sorted(i["engagement"] for i in items)[len(items) // 2]
        for i in items:
            hi_e = i["engagement"] >= med
            hi_s = i["substantive_value"] >= 3.0
            i["quadrant"] = ("high engagement + high substance" if hi_e and hi_s else "high engagement + low substance" if hi_e else "low engagement + high substance" if hi_s else "low engagement + low substance")
    return {"items": items, "published_count": len(rows), "with_metrics": len(items)}
