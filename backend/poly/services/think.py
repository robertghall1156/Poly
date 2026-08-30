"""Think Mode: an interview that helps develop a position before any content is written."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Claim, PositionBrief, Principle, PrincipleRevision, Story, ThinkSession
from ..providers.registry import Router
from .llm_utils import as_list, as_str, chat_json
from .principles import principle_summary_text
from .search import embed_entity, search
from .voice import INTEGRITY, principles_block

INTERVIEW_STAGES = [
    ("instinct", "identify the owner's initial instinct"),
    ("principles", "compare that instinct with the owner's existing principles and name any tension or contradiction"),
    ("opposing", "present the strongest opposing argument and ask how the owner responds"),
    ("assumptions", "challenge the weakest assumption in what the owner has said so far"),
    ("facts", "identify a factual claim that needs verification and ask what evidence would change their mind"),
    ("tradeoffs", "ask which tradeoffs the owner is willing to accept"),
    ("position", "ask the owner to state their position in one or two sentences"),
]

SYSTEM_QUESTION = f"""You are a rigorous, friendly thinking partner. You interview the owner ONE question at a time
to help them develop a position. You do not write content. You do not flatter. You push on weak reasoning.
{INTEGRITY}
Return JSON: {{"question": "<one substantive question, max 60 words>", "kind": "<stage name>",
"note": "<optional one-sentence observation about a contradiction or gap, or empty>"}}"""

SYSTEM_BRIEF = f"""You turn a Think Mode interview into a Position Brief in the owner's own reasoning. Be faithful to
what the owner actually said; where they were uncertain, keep the uncertainty. {INTEGRITY}
Return JSON with keys: issue, position, rationale, governing_principle (title of the most relevant existing principle or
a proposed new one), strongest_for, strongest_against, response (how the owner answers the strongest against),
factual_assumptions (list), unresolved_questions (list), policy_mechanisms (list of concrete mechanisms),
confidence (0-1)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _context(db: Session, session: ThinkSession, router: Router) -> tuple[str, list[Principle]]:
    parts = []
    if session.story_id:
        story = db.get(Story, session.story_id)
        if story:
            parts.append(f"STORY: {story.title}\nSummary: {story.summary}\nWhy it matters: {story.why_it_matters}")
            claims = db.execute(select(Claim).where(Claim.story_id == story.id).limit(12)).scalars().all()
            if claims:
                parts.append("CLAIMS:\n" + "\n".join(f"- [{c.claim_type}] {c.text}" for c in claims))
            if story.arguments:
                parts.append("ARGUMENTS:\n" + "\n".join(f"- ({a.get('side')}) {a.get('argument')}" for a in story.arguments if isinstance(a, dict)))
    if session.question:
        parts.append(f"QUESTION UNDER CONSIDERATION: {session.question}")
    # relevant principles via hybrid search + explicitly linked principle
    query = session.question or session.title
    hits = search(db, query, types=["principle"], limit=6, router=router)
    ids = [h.entity_id for h in hits]
    if session.principle_id and session.principle_id not in ids:
        ids.insert(0, session.principle_id)
    principles = [p for p in (db.get(Principle, i) for i in ids) if p]
    session.principle_ids_considered = [p.id for p in principles]
    parts.append("RELEVANT PRINCIPLES:\n" + principles_block(principles))
    return "\n\n".join(parts), principles


def _transcript(session: ThinkSession) -> str:
    lines = []
    for m in session.messages or []:
        who = "OWNER" if m.get("role") == "user" else "INTERVIEWER"
        lines.append(f"{who}: {m.get('content', '')}")
    return "\n".join(lines) or "(no exchanges yet)"


def start_session(db: Session, *, title: str, story_id: str | None = None, principle_id: str | None = None, question: str = "") -> ThinkSession:
    s = ThinkSession(title=title, story_id=story_id, principle_id=principle_id, question=question, messages=[])
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def next_question(db: Session, session: ThinkSession, router: Router | None = None) -> dict[str, Any]:
    router = router or Router(db)
    context, _ = _context(db, session, router)
    asked = sum(1 for m in session.messages or [] if m.get("role") == "assistant")
    stage = INTERVIEW_STAGES[min(asked, len(INTERVIEW_STAGES) - 1)]
    user = (
        f"{context}\n\nTRANSCRIPT SO FAR:\n{_transcript(session)}\n\n"
        f"Stage {asked + 1} of {len(INTERVIEW_STAGES)} — your job now: {stage[1]}. Ask exactly one question."
    )
    data, res = chat_json(router, "REASONING", "think_question", SYSTEM_QUESTION, user, temperature=0.5, max_tokens=400)
    q = as_str(data.get("question")).strip() or "What is your initial instinct here, and why?"
    msg = {"role": "assistant", "content": q, "kind": as_str(data.get("kind")) or stage[0], "note": as_str(data.get("note")), "created_at": _now().isoformat()}
    session.messages = [*(session.messages or []), msg]
    session.model_used = res.model
    db.commit()
    return msg


def answer(db: Session, session: ThinkSession, text: str) -> ThinkSession:
    session.messages = [*(session.messages or []), {"role": "user", "content": text.strip(), "kind": "answer", "created_at": _now().isoformat()}]
    db.commit()
    return session


def generate_brief(db: Session, session: ThinkSession, router: Router | None = None) -> PositionBrief:
    router = router or Router(db)
    context, principles = _context(db, session, router)
    user = f"{context}\n\nINTERVIEW TRANSCRIPT:\n{_transcript(session)}"
    data, res = chat_json(router, "REASONING", "position_brief", SYSTEM_BRIEF, user, temperature=0.3, max_tokens=1800)
    gov_title = as_str(data.get("governing_principle"))
    gov = next((p for p in principles if p.title.lower() == gov_title.lower()), None)
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    brief = PositionBrief(
        think_session_id=session.id,
        story_id=session.story_id,
        issue=as_str(data.get("issue")) or session.title,
        position=as_str(data.get("position")),
        rationale=as_str(data.get("rationale")),
        governing_principle_id=gov.id if gov else (session.principle_id or None),
        governing_principle_text=gov_title,
        strongest_for=as_str(data.get("strongest_for")),
        strongest_against=as_str(data.get("strongest_against")),
        response=as_str(data.get("response")),
        factual_assumptions=[as_str(x) for x in as_list(data.get("factual_assumptions"))],
        unresolved_questions=[as_str(x) for x in as_list(data.get("unresolved_questions"))],
        policy_mechanisms=[as_str(x) for x in as_list(data.get("policy_mechanisms"))],
        confidence=max(0.0, min(1.0, conf)),
    )
    db.add(brief)
    session.status = "completed"
    session.model_used = res.model
    db.commit()
    db.refresh(brief)
    embed_entity(db, "position_brief", brief, router)
    return brief


def approve_brief(db: Session, brief: PositionBrief, *, mode: str = "auto", principle_id: str | None = None, title: str | None = None, category: str | None = None, reason: str = "") -> Principle:
    """Write the brief into the operating system.

    mode: "auto" (revise governing principle if it exists, else create), "revise", or "new".
    """
    target: Principle | None = None
    if mode in ("auto", "revise"):
        pid = principle_id or brief.governing_principle_id
        target = db.get(Principle, pid) if pid else None
    if target is not None and mode != "new":
        if target.current_position != brief.position:
            db.add(PrincipleRevision(principle_id=target.id, old_position=target.current_position, new_position=brief.position, old_status=target.status, new_status=target.status, reason_for_change=reason or f"Approved position brief: {brief.issue}"))
            target.current_position = brief.position
        if brief.rationale:
            target.rationale = brief.rationale
        target.confidence = brief.confidence
    else:
        target = Principle(
            title=title or brief.governing_principle_text or brief.issue[:120],
            category=category or "Positions",
            current_position=brief.position,
            rationale=brief.rationale,
            status="provisional",
            confidence=brief.confidence,
        )
        db.add(target)
        db.flush()
        db.add(PrincipleRevision(principle_id=target.id, old_position="", new_position=brief.position, new_status="provisional", reason_for_change=reason or f"Created from position brief: {brief.issue}"))
    if brief.strongest_against:
        from ..models import Counterargument

        db.add(Counterargument(principle_id=target.id, argument=brief.strongest_against, strength="strong", response=brief.response, unresolved_questions=brief.unresolved_questions, source="Think Mode"))
    brief.status = "approved"
    brief.approved_principle_id = target.id
    brief.approved_at = _now()
    if brief.session:
        brief.session.status = "approved"
    db.commit()
    db.refresh(target)
    embed_entity(db, "principle", target)
    return target


def brief_to_markdown(brief: PositionBrief) -> str:
    lines = [f"# Position Brief: {brief.issue}", "", f"**Position.** {brief.position}", "", f"**Rationale.** {brief.rationale}", ""]
    if brief.governing_principle_text:
        lines += [f"**Governing principle.** {brief.governing_principle_text}", ""]
    lines += [f"**Strongest argument for.** {brief.strongest_for}", "", f"**Strongest argument against.** {brief.strongest_against}", "", f"**Response.** {brief.response}", ""]
    for label, items in (("Factual assumptions", brief.factual_assumptions), ("Unresolved questions", brief.unresolved_questions), ("Possible policy mechanisms", brief.policy_mechanisms)):
        if items:
            lines.append(f"## {label}")
            lines += [f"- {i}" for i in items]
            lines.append("")
    lines.append(f"Confidence: {brief.confidence:.0%}")
    return "\n".join(lines)


__all__ = ["start_session", "next_question", "answer", "generate_brief", "approve_brief", "brief_to_markdown", "principle_summary_text"]
