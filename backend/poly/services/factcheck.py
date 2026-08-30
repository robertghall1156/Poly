"""Fact check gate.

Extracts factual assertions from a script (local model), labels each one, and blocks READY
while unresolved assertions remain — unless the owner records an explicit override reason.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Claim, ContentItem, FactCheckClaim, Story
from ..providers.base import ProviderError
from ..providers.registry import Router
from .llm_utils import as_list, as_str, chat_json
from .voice import INTEGRITY

STATUSES = ["VERIFIED", "SUPPORTED_BUT_UNCERTAIN", "OPINION", "COUNTERFACTUAL", "UNVERIFIED", "OUTDATED"]
UNRESOLVED = {"UNVERIFIED", "OUTDATED", "SUPPORTED_BUT_UNCERTAIN"}

SYSTEM = f"""You are a meticulous fact checker. {INTEGRITY}
Extract EVERY factual assertion in the script (numbers, dates, events, attributions, causal claims stated as fact).
For each, using ONLY the provided source material, label status as one of: VERIFIED (directly supported by a
provided source), SUPPORTED_BUT_UNCERTAIN (partially supported or dated), OPINION (a judgement, not checkable),
COUNTERFACTUAL (a hypothetical), UNVERIFIED (no supporting source provided), OUTDATED (source shows it changed).
Return JSON: {{"claims": [{{"text", "status", "sources": [urls], "notes"}}]}}. Never invent sources."""

_NUMERIC = re.compile(r"\d[\d,.%$]*")


def heuristic_extract(script: str) -> list[dict[str, Any]]:
    """No-model fallback: sentences with numbers/dates/attributions become UNVERIFIED claims."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", script or ""):
        s = sent.strip()
        if len(s) < 20 or s.startswith("#"):
            continue
        if _NUMERIC.search(s) or re.search(r"\b(according to|reported|said|found|announced|passed|ruled|signed)\b", s, re.I):
            out.append({"text": s[:500], "status": "UNVERIFIED", "sources": [], "notes": "Extracted heuristically (no local model available)."})
    return out[:40]


def run_fact_check(db: Session, item: ContentItem, router: Router | None = None) -> list[FactCheckClaim]:
    router = router or Router(db)
    material = []
    if item.story_id:
        story = db.get(Story, item.story_id)
        if story:
            for a in [a for a in story.articles if not a.duplicate_of_id][:8]:
                material.append(f"SOURCE: {a.publication} — {a.title} — {a.url}\n{(a.content or a.summary)[:1500]}")
            claims = db.execute(select(Claim).where(Claim.story_id == story.id)).scalars().all()
            if claims:
                material.append("EXTRACTED CLAIMS:\n" + "\n".join(f"- [{c.claim_type}] {c.text} ({c.source_url})" for c in claims))
    user = f"SCRIPT:\n{item.script[:12000]}\n\nSOURCE MATERIAL:\n" + ("\n\n".join(material) or "(none provided)")
    try:
        data, res = chat_json(router, "REASONING", "factcheck", SYSTEM, user, temperature=0.0, max_tokens=3000)
        rows = [c for c in as_list(data.get("claims")) if isinstance(c, dict) and c.get("text")]
        model = res.model
    except (ProviderError, ValueError):
        rows = heuristic_extract(item.script)
        model = "heuristic"
    db.query(FactCheckClaim).filter(FactCheckClaim.content_item_id == item.id).delete()
    created = []
    for c in rows:
        status = as_str(c.get("status")).upper().replace(" ", "_")
        if status not in STATUSES:
            status = "UNVERIFIED"
        fc = FactCheckClaim(content_item_id=item.id, text=as_str(c["text"])[:1000], status=status, sources=[as_str(s) for s in as_list(c.get("sources"))], notes=as_str(c.get("notes"))[:1000], resolved=status not in UNRESOLVED)
        db.add(fc)
        created.append(fc)
    item.fact_check_status = "fact_checked" if all(c.resolved for c in created) else "pending"
    meta = dict(item.generation_meta or {})
    meta["fact_check_model"] = model
    item.generation_meta = meta
    db.commit()
    db.refresh(item)
    return created


def resolve_claim(db: Session, claim: FactCheckClaim, *, status: str, sources: list[str] | None = None, notes: str = "") -> FactCheckClaim:
    if status not in STATUSES:
        raise ValueError("bad status")
    claim.status = status
    if sources is not None:
        claim.sources = sources
    if notes:
        claim.notes = notes
    claim.resolved = status not in UNRESOLVED
    item = claim.content_item
    db.flush()
    siblings = db.execute(select(FactCheckClaim).where(FactCheckClaim.content_item_id == item.id)).scalars().all()
    if all(c.resolved for c in siblings):
        item.fact_check_status = "fact_checked"
    db.commit()
    return claim


def can_mark_ready(db: Session, item: ContentItem, *, override_reason: str = "") -> tuple[bool, str]:
    if item.format in {"meme", "infographic", "book_note", "research_brief"}:
        return True, ""
    claims = db.execute(select(FactCheckClaim).where(FactCheckClaim.content_item_id == item.id)).scalars().all()
    if item.fact_check_status == "not_run":
        if override_reason:
            item.fact_check_status = "overridden"
            item.fact_check_override_reason = override_reason
            return True, ""
        return False, "Run Fact Check before marking this READY (or provide an explicit override reason)."
    unresolved = [c for c in claims if not c.resolved]
    if unresolved and item.fact_check_status != "overridden":
        if override_reason:
            item.fact_check_status = "overridden"
            item.fact_check_override_reason = override_reason
            return True, ""
        return False, f"{len(unresolved)} unresolved factual assertion(s). Resolve them or override with a reason."
    return True, ""
