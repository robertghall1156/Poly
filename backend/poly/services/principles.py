"""Political operating system: principles, revisions, evidence, counterarguments,
and the two-way bridge to `knowledge/political_operating_system.md`."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Counterargument, Principle, PrincipleRevision, SupportingEvidence

_META = re.compile(r"^-\s*(status|confidence)\s*:\s*(.+)$", re.I)


def parse_markdown(text: str) -> list[dict[str, Any]]:
    """Parse the operating-system markdown into principle dicts (see file header for format)."""
    principles: list[dict[str, Any]] = []
    category = "General"
    current: dict[str, Any] | None = None
    section = None  # "position" | "rationale" | None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            category = line[3:].strip()
            current = None
            continue
        if line.startswith("### "):
            current = {"title": line[4:].strip(), "category": category, "status": "provisional", "confidence": 0.6, "current_position": "", "rationale": ""}
            principles.append(current)
            section = None
            continue
        if current is None:
            continue
        m = _META.match(line)
        if m:
            key, val = m.group(1).lower(), m.group(2).strip()
            if key == "status":
                current["status"] = val.lower()
            else:
                try:
                    current["confidence"] = float(val)
                except ValueError:
                    pass
            continue
        low = line.lower()
        if low.startswith("position:"):
            section = "position"
            current["current_position"] = line.split(":", 1)[1].strip()
            continue
        if low.startswith("rationale:"):
            section = "rationale"
            current["rationale"] = line.split(":", 1)[1].strip()
            continue
        if line.strip() == "---":
            continue
        if section == "position" and line.strip():
            current["current_position"] += ("\n" if current["current_position"] else "") + line.strip()
        elif section == "rationale" and line.strip():
            current["rationale"] += ("\n" if current["rationale"] else "") + line.strip()
    return [p for p in principles if p["current_position"]]


def to_markdown(principles: list[Principle]) -> str:
    lines = [
        "# Political Operating System",
        "",
        "Exported by Poly. Each `##` heading is a category; each `###` heading is a principle.",
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')}.",
        "",
        "---",
        "",
    ]
    by_cat: dict[str, list[Principle]] = {}
    for p in sorted(principles, key=lambda x: (x.sort_order, x.created_at)):
        by_cat.setdefault(p.category, []).append(p)
    for cat, items in by_cat.items():
        lines.append(f"## {cat}")
        lines.append("")
        for p in items:
            lines += [f"### {p.title}", f"- status: {p.status}", f"- confidence: {p.confidence:.2f}", "", f"Position: {p.current_position}", ""]
            if p.rationale:
                lines += [f"Rationale: {p.rationale}", ""]
    return "\n".join(lines)


def import_markdown(db: Session, path: Path | None = None, *, only_if_empty: bool = False) -> dict[str, int]:
    """Create/update principles from the markdown file. Matching is by (category, title)."""
    path = path or get_settings().knowledge_path
    if not path.exists():
        return {"created": 0, "updated": 0, "skipped": 0}
    if only_if_empty and db.execute(select(Principle.id).limit(1)).first():
        return {"created": 0, "updated": 0, "skipped": -1}
    parsed = parse_markdown(path.read_text(encoding="utf-8"))
    created = updated = skipped = 0
    existing = {(p.category.lower(), p.title.lower()): p for p in db.execute(select(Principle)).scalars()}
    for i, item in enumerate(parsed):
        key = (item["category"].lower(), item["title"].lower())
        row = existing.get(key)
        if row is None:
            db.add(Principle(sort_order=i, **item))
            created += 1
        elif row.current_position != item["current_position"] or row.rationale != item["rationale"]:
            db.add(PrincipleRevision(principle_id=row.id, old_position=row.current_position, new_position=item["current_position"], old_status=row.status, new_status=item["status"], reason_for_change="Imported from political_operating_system.md"))
            row.current_position = item["current_position"]
            row.rationale = item["rationale"]
            row.status = item["status"]
            row.confidence = item["confidence"]
            updated += 1
        else:
            skipped += 1
    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


def export_markdown(db: Session, path: Path | None = None) -> Path:
    path = path or get_settings().knowledge_path
    rows = db.execute(select(Principle).where(Principle.status != "retired")).scalars().all()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(rows), encoding="utf-8")
    return path


# ---- CRUD ----------------------------------------------------------------
def list_principles(db: Session, *, category: str | None = None, status: str | None = None) -> list[Principle]:
    q = select(Principle)
    if category:
        q = q.where(Principle.category == category)
    if status:
        q = q.where(Principle.status == status)
    return list(db.execute(q.order_by(Principle.sort_order, Principle.created_at)).scalars())


def create_principle(db: Session, data: dict[str, Any]) -> Principle:
    p = Principle(**{k: v for k, v in data.items() if k in Principle.__table__.columns.keys()})
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def update_principle(db: Session, principle: Principle, data: dict[str, Any], *, reason: str = "") -> Principle:
    new_pos = data.get("current_position")
    new_status = data.get("status")
    changed = (new_pos is not None and new_pos != principle.current_position) or (new_status is not None and new_status != principle.status)
    if changed:
        db.add(
            PrincipleRevision(
                principle_id=principle.id,
                old_position=principle.current_position,
                new_position=new_pos if new_pos is not None else principle.current_position,
                old_status=principle.status,
                new_status=new_status or principle.status,
                reason_for_change=reason or data.get("reason_for_change", "") or "Edited",
            )
        )
    for k in ("title", "category", "current_position", "rationale", "status", "confidence", "sort_order"):
        if k in data and data[k] is not None:
            setattr(principle, k, data[k])
    db.commit()
    db.refresh(principle)
    return principle


def add_evidence(db: Session, principle: Principle, data: dict[str, Any]) -> SupportingEvidence:
    ev = SupportingEvidence(principle_id=principle.id, **{k: v for k, v in data.items() if k in SupportingEvidence.__table__.columns.keys() and k != "id"})
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def add_counterargument(db: Session, principle: Principle, data: dict[str, Any]) -> Counterargument:
    ca = Counterargument(principle_id=principle.id, **{k: v for k, v in data.items() if k in Counterargument.__table__.columns.keys() and k != "id"})
    db.add(ca)
    db.commit()
    db.refresh(ca)
    return ca


def principle_summary_text(p: Principle) -> str:
    return f"{p.title} [{p.category}] — {p.current_position}"
