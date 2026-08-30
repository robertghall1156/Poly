"""Content engine: long-form packages, social derivatives, lineage, calendar, book links."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CONTENT_FORMATS, CONTENT_STATUSES, Claim, ContentItem, PositionBrief, Principle, Story
from ..providers.registry import Router
from .llm_utils import as_list, as_str, chat_json
from .search import embed_entity
from .voice import INTEGRITY, VOICE, principles_block

LONGFORM_SECTIONS = [
    "QUESTION", "WHY PEOPLE CARE", "HOW THE CURRENT SYSTEM WORKS", "HOW WE GOT HERE", "WHAT IS WORKING",
    "WHAT IS BROKEN", "STRONGEST COUNTERARGUMENT", "MY VIEW", "WHAT I WOULD CHANGE", "WHAT COULD GO WRONG", "CONCLUSION",
]
LONG_FORMATS = {"podcast", "youtube", "newsletter", "article"}
SHORT_VIDEO = {"youtube_short", "tiktok", "instagram_reel"}
SOCIAL_TEXT = {"x_post", "x_thread", "facebook_post", "instagram_post", "linkedin_post"}

SYSTEM_LONGFORM = f"""{VOICE}
{INTEGRITY}
Produce a complete long-form episode package as JSON with keys:
working_title, alternative_titles (5), hook (2 sentences), opening_30s (spoken, ~80 words), thesis,
outline (list of {{section, notes}} using EXACTLY these sections in order: {'; '.join(LONGFORM_SECTIONS)}),
research_needed (list), arguments (list), counterarguments (list, steelmanned), examples (list), evidence (list —
only from provided material, otherwise phrase as "needs verification: ..."), transitions (list), conclusion,
call_to_discussion, show_notes (markdown), sources (list of URLs from the material)."""

SYSTEM_SOCIAL = f"""{VOICE}
{INTEGRITY}
From the long-form material, produce derivatives as JSON with keys:
posts (3-5 short standalone text posts, ≤280 chars each), thread (list of 6-10 numbered tweets),
quote_cards (3 short quotable lines actually present in or faithful to the material),
short_video_ideas (3-5, each one sentence: the moment + why it works vertical), hooks (5), titles (5),
thumbnail_text (3, ≤5 words each, not misleading), meme_concepts (3 — describe format + text; no fabricated quotes)."""

SYSTEM_SHORT = f"""{VOICE}
{INTEGRITY}
Write a 45-60 second vertical video script as JSON with keys: title, hook (first 3 seconds, spoken), script (spoken,
~130 words, one self-contained idea), on_screen_text (list of 3-5 short overlays), caption (≤150 chars), hashtags (5),
cta (one line)."""

SYSTEM_TEXT_POST = f"""{VOICE}
{INTEGRITY}
Write the requested platform post as JSON with keys: title, body (the post text in the platform's natural length and
tone), alternatives (2 shorter variants), hashtags (list, may be empty)."""

SYSTEM_TALKING = f"""{VOICE}
{INTEGRITY}
Produce talking points as JSON: {{title, points (8-12 crisp bullets), anticipated_questions (5 with short answers),
numbers_to_verify (list)}}."""

SYSTEM_BOOKNOTE = f"""{VOICE}
{INTEGRITY}
Write a book note as JSON: {{title, theme, note (300-500 words in the owner's voice connecting this to the larger system
argument), chapter_fit (suggested chapter theme), personal_story_prompt (a question to prompt a personal anecdote)}}."""


def _now() -> datetime:
    return datetime.now(UTC)


def _material(db: Session, *, story: Story | None, brief: PositionBrief | None, principles: list[Principle], parent: ContentItem | None) -> str:
    parts = []
    if story:
        parts.append(f"STORY: {story.title}\nSummary: {story.summary}\nWhy it matters: {story.why_it_matters}")
        claims = db.execute(select(Claim).where(Claim.story_id == story.id).limit(15)).scalars().all()
        if claims:
            parts.append("CLAIMS (with provenance):\n" + "\n".join(f"- [{c.claim_type}] {c.text} ({c.publication} {c.source_url})" for c in claims))
        if story.arguments:
            parts.append("ARGUMENTS:\n" + "\n".join(f"- ({a.get('side')}) {a.get('argument')}" for a in story.arguments if isinstance(a, dict)))
        srcs = [a for a in story.articles if not a.duplicate_of_id][:8]
        if srcs:
            parts.append("SOURCES:\n" + "\n".join(f"- {a.publication}: {a.title} — {a.url}" for a in srcs))
    if brief:
        parts.append(
            f"POSITION BRIEF:\nIssue: {brief.issue}\nPosition: {brief.position}\nRationale: {brief.rationale}\n"
            f"Strongest for: {brief.strongest_for}\nStrongest against: {brief.strongest_against}\nResponse: {brief.response}\n"
            f"Assumptions: {brief.factual_assumptions}\nUnresolved: {brief.unresolved_questions}\nMechanisms: {brief.policy_mechanisms}"
        )
    if principles:
        parts.append("PRINCIPLES:\n" + principles_block(principles))
    if parent:
        parts.append(f"PARENT CONTENT ({parent.format}): {parent.title}\n{(parent.script or json.dumps(parent.package))[:6000]}")
    return "\n\n".join(parts) or "(no material provided)"


def _script_from_longform(pkg: dict[str, Any]) -> str:
    lines = [f"# {pkg.get('working_title', '')}", "", f"HOOK: {pkg.get('hook', '')}", "", f"OPENING: {pkg.get('opening_30s', '')}", "", f"THESIS: {pkg.get('thesis', '')}", ""]
    for sec in as_list(pkg.get("outline")):
        if isinstance(sec, dict):
            lines += [f"## {sec.get('section', '')}", as_str(sec.get("notes")), ""]
    lines += ["## CONCLUSION", as_str(pkg.get("conclusion")), "", f"CALL TO DISCUSSION: {pkg.get('call_to_discussion', '')}"]
    return "\n".join(lines)


def create_item(db: Session, data: dict[str, Any]) -> ContentItem:
    if data.get("format") not in CONTENT_FORMATS:
        raise ValueError(f"unknown format {data.get('format')}")
    if data.get("status") and data["status"] not in CONTENT_STATUSES:
        raise ValueError(f"unknown status {data['status']}")
    item = ContentItem(**{k: v for k, v in data.items() if k in ContentItem.__table__.columns.keys() and k != "id"})
    db.add(item)
    db.commit()
    db.refresh(item)
    embed_entity(db, "content_item", item)
    return item


def generate(db: Session, *, fmt: str, story_id: str | None = None, brief_id: str | None = None, principle_ids: list[str] | None = None, parent_id: str | None = None, title: str | None = None, extra_instructions: str = "", router: Router | None = None) -> ContentItem:
    """Generate a content item of `fmt` from story/brief/parent material using the local WRITING model."""
    if fmt not in CONTENT_FORMATS:
        raise ValueError(f"unknown format {fmt}")
    router = router or Router(db)
    story = db.get(Story, story_id) if story_id else None
    brief = db.get(PositionBrief, brief_id) if brief_id else None
    parent = db.get(ContentItem, parent_id) if parent_id else None
    pids = list(principle_ids or [])
    if brief and brief.governing_principle_id and brief.governing_principle_id not in pids:
        pids.append(brief.governing_principle_id)
    if story and not pids:
        pids = [l.principle_id for l in story.principle_links][:4]
    if parent and not pids:
        pids = list(parent.principle_ids or [])
    principles = [p for p in (db.get(Principle, i) for i in pids) if p]
    material = _material(db, story=story, brief=brief, principles=principles, parent=parent)
    if extra_instructions:
        material += f"\n\nADDITIONAL INSTRUCTIONS: {extra_instructions}"

    if fmt in LONG_FORMATS or fmt == "research_brief":
        sys, tag, task = SYSTEM_LONGFORM, "longform", "WRITING"
    elif fmt in SHORT_VIDEO:
        sys, tag, task = SYSTEM_SHORT, "short", "WRITING"
    elif fmt in SOCIAL_TEXT:
        sys, tag, task = SYSTEM_TEXT_POST + f"\nPlatform: {fmt}.", "text_post", "FAST"
    elif fmt == "talking_points":
        sys, tag, task = SYSTEM_TALKING, "talking", "WRITING"
    elif fmt == "book_note":
        sys, tag, task = SYSTEM_BOOKNOTE, "booknote", "WRITING"
    elif fmt in {"meme", "infographic"}:
        sys, tag, task = (
            f"{VOICE}\n{INTEGRITY}\nProduce 3 {fmt} concepts as JSON: {{title, concepts (list of {{headline, text, visual, data_needed}})}}. No fabricated quotes or numbers.",
            "visual_concepts",
            "FAST",
        )
    else:
        sys, tag, task = SYSTEM_LONGFORM, "longform", "WRITING"

    data, res = chat_json(router, task, tag, sys, material, temperature=0.6, max_tokens=4000)
    item_title = title or as_str(data.get("working_title") or data.get("title")) or (story.title if story else (brief.issue if brief else fmt))
    script = _script_from_longform(data) if tag == "longform" else as_str(data.get("script") or data.get("body") or data.get("note") or "")
    if tag == "talking":
        script = "\n".join(f"- {p}" for p in as_list(data.get("points")))
    item = ContentItem(
        title=item_title[:400],
        format=fmt,
        status="SCRIPTING" if script else "IDEA",
        story_id=story_id or (parent.story_id if parent else None),
        principle_ids=pids,
        position_brief_id=brief_id or (parent.position_brief_id if parent else None),
        script=script,
        package=data,
        parent_id=parent_id,
        platform=fmt,
        generation_meta={"model": res.model, "provider": res.provider, "task": task, "generated_at": _now().isoformat(), "locality": res.raw.get("locality", "local")},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    embed_entity(db, "content_item", item, router)
    return item


def generate_social_bundle(db: Session, parent: ContentItem, router: Router | None = None) -> dict[str, Any]:
    """3-5 posts, thread, quote cards, short video ideas, hooks, titles, thumbnail text, meme concepts.
    Stored on the parent (`package.social`) and also materialised as child ContentItems for posts/thread."""
    router = router or Router(db)
    principles = [p for p in (db.get(Principle, i) for i in (parent.principle_ids or [])) if p]
    story = db.get(Story, parent.story_id) if parent.story_id else None
    material = _material(db, story=story, brief=None, principles=principles, parent=parent)
    data, res = chat_json(router, "WRITING", "social", SYSTEM_SOCIAL, material, temperature=0.7, max_tokens=2500)
    pkg = dict(parent.package or {})
    pkg["social"] = data
    parent.package = pkg
    children = []
    for i, post in enumerate(as_list(data.get("posts"))[:5]):
        children.append(ContentItem(title=f"{parent.title} — post {i + 1}", format="x_post", status="SCRIPTING", story_id=parent.story_id, principle_ids=parent.principle_ids, script=as_str(post), parent_id=parent.id, platform="x", generation_meta={"model": res.model}))
    thread = as_list(data.get("thread"))
    if thread:
        children.append(ContentItem(title=f"{parent.title} — thread", format="x_thread", status="SCRIPTING", story_id=parent.story_id, principle_ids=parent.principle_ids, script="\n\n".join(as_str(t) for t in thread), package={"thread": thread}, parent_id=parent.id, platform="x", generation_meta={"model": res.model}))
    for i, idea in enumerate(as_list(data.get("short_video_ideas"))[:5]):
        children.append(ContentItem(title=f"{parent.title} — short idea {i + 1}", format="youtube_short", status="IDEA", story_id=parent.story_id, principle_ids=parent.principle_ids, script=as_str(idea), parent_id=parent.id, platform="youtube_short", generation_meta={"model": res.model}))
    for i, meme in enumerate(as_list(data.get("meme_concepts"))[:3]):
        children.append(ContentItem(title=f"{parent.title} — meme {i + 1}", format="meme", status="IDEA", story_id=parent.story_id, principle_ids=parent.principle_ids, script=as_str(meme), parent_id=parent.id, platform="meme", generation_meta={"model": res.model}))
    for c in children:
        db.add(c)
    db.commit()
    for c in children:
        embed_entity(db, "content_item", c, router)
    return {"social": data, "children": [c.id for c in children]}


def content_tree(db: Session, root: ContentItem) -> dict[str, Any]:
    def node(item: ContentItem) -> dict[str, Any]:
        return {
            "id": item.id, "title": item.title, "format": item.format, "status": item.status, "platform": item.platform,
            "children": [node(c) for c in sorted(item.children, key=lambda c: c.created_at)],
        }

    while root.parent is not None:
        root = root.parent
    return node(root)


def set_status(db: Session, item: ContentItem, status: str, *, override_reason: str = "") -> ContentItem:
    if status not in CONTENT_STATUSES:
        raise ValueError(f"unknown status {status}")
    if status in ("READY", "PUBLISHED"):
        from .factcheck import can_mark_ready

        ok, why = can_mark_ready(db, item, override_reason=override_reason)
        if not ok:
            raise PermissionError(why)
        if status == "READY" and not item.approved_at:
            item.approved_at = _now()
    item.status = status
    db.commit()
    return item


def lineage(db: Session, item: ContentItem) -> dict[str, Any]:
    """Everything this item descends from: story, brief, principles, video/clip, parent chain."""
    chain = []
    cur = item.parent
    while cur:
        chain.append({"id": cur.id, "title": cur.title, "format": cur.format})
        cur = cur.parent
    story = db.get(Story, item.story_id) if item.story_id else None
    brief = db.get(PositionBrief, item.position_brief_id) if item.position_brief_id else None
    principles = [p for p in (db.get(Principle, i) for i in (item.principle_ids or [])) if p]
    return {
        "parents": chain,
        "story": {"id": story.id, "title": story.title} if story else None,
        "brief": {"id": brief.id, "issue": brief.issue} if brief else None,
        "principles": [{"id": p.id, "title": p.title} for p in principles],
        "source_video_id": item.source_video_id,
        "clip_id": item.clip_id,
        "children": [{"id": c.id, "title": c.title, "format": c.format, "status": c.status} for c in item.children],
    }
