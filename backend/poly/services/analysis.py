"""Story analysis: claims, topics, relevance to principles, arguments, content opportunities.

Two layers:
1. Heuristic (always runs, no model): topics, principle links by similarity + category mapping,
   primary-source detection, relevance score.
2. Local LLM enrichment (when a FAST/REASONING model is available): summary, why it matters,
   typed claims with supporting passages, arguments on multiple sides, unresolved questions,
   competing interpretations, content opportunities. Failure never blocks ingestion; the story is
   left at `analysis_source='heuristic'` and picked up again later.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Claim, Principle, Story, StoryEvent, StoryPrincipleLink
from ..providers.base import ProviderError
from ..providers.registry import Router
from .llm_utils import as_list, as_str, chat_json
from .search import embed_entity
from .topics import TOPIC_LIST, normalize_topics
from .voice import INTEGRITY, principles_block

log = logging.getLogger(__name__)

# topic → principle categories that usually apply
TOPIC_CATEGORY_MAP: dict[str, list[str]] = {
    "government": ["Government"],
    "elections": ["Government", "Money and political power"],
    "congress": ["Government"],
    "presidency": ["Government"],
    "courts": ["Government"],
    "taxes": ["Taxation", "Capitalism and wealth"],
    "wealth": ["Capitalism and wealth", "Taxation", "Money and political power"],
    "corporate power": ["Capitalism and wealth", "Money and political power", "Workers and corporations"],
    "labor": ["Workers and corporations", "Unions", "Social floor"],
    "executive compensation": ["Executive compensation", "Workers and corporations"],
    "ai": ["AI and automation", "Workers and corporations"],
    "automation": ["AI and automation"],
    "healthcare": ["Healthcare", "Social floor"],
    "education": ["Education", "Social floor"],
    "immigration": ["Immigration"],
    "defense": ["Defense and foreign policy"],
    "veterans": ["Defense and foreign policy", "Social floor"],
    "foreign policy": ["Defense and foreign policy"],
    "technology": ["AI and automation", "Capitalism and wealth"],
    "economic policy": ["Capitalism and wealth", "Taxation", "Social floor"],
    "housing": ["Social floor"],
    "energy": ["Government"],
    "infrastructure": ["Government"],
}

CLAIM_TYPES = {"FACT", "ANALYSIS", "OPINION", "COUNTERFACTUAL", "PREDICTION"}
FORMATS = ["podcast", "youtube", "youtube_short", "x_thread", "linkedin_post", "newsletter", "article", "talking_points", "infographic", "meme", "book_note"]


def _cos(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.asarray(a, dtype="float32"), np.asarray(b, dtype="float32")
    d = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
    return float(va @ vb / d)


def link_principles(db: Session, story: Story, router: Router, *, max_links: int = 5) -> list[StoryPrincipleLink]:
    principles = db.execute(select(Principle).where(Principle.status != "retired")).scalars().all()
    if not principles:
        return []
    story_text = f"{story.title}. {story.summary} {' '.join(story.keywords or [])}"
    texts = [story_text] + [f"{p.title}. {p.current_position}" for p in principles]
    vecs, _ = router.embed(texts)
    sv, pvecs = vecs[0], vecs[1:]
    wanted_cats = set()
    for t in story.topics or []:
        wanted_cats.update(c.lower() for c in TOPIC_CATEGORY_MAP.get(t, []))
    scored = []
    for p, pv in zip(principles, pvecs):
        sim = max(0.0, _cos(sv, pv))
        cat = 1.0 if p.category.lower() in wanted_cats else 0.0
        score = 0.6 * sim + 0.4 * cat
        if score >= 0.25:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    db.query(StoryPrincipleLink).filter(StoryPrincipleLink.story_id == story.id).delete()
    links = []
    for score, p in scored[:max_links]:
        link = StoryPrincipleLink(story_id=story.id, principle_id=p.id, relation="relates", strength=round(min(1.0, score), 3))
        db.add(link)
        links.append(link)
    db.flush()
    return links


def heuristic_analysis(db: Session, story: Story, router: Router) -> None:
    arts = [a for a in story.articles if not a.duplicate_of_id]
    topics: list[str] = list(story.topics or [])
    for a in arts:
        for t in a.topics or []:
            if t not in topics:
                topics.append(t)
    story.topics = topics[:8]
    if not story.summary and arts:
        story.summary = (arts[0].summary or arts[0].title)[:600]
    prim = []
    for a in arts:
        if a.source and a.source.is_primary:
            prim.append({"title": a.title, "url": a.url, "publication": a.publication})
    story.primary_sources = prim[:10]
    links = link_principles(db, story, router)
    top = max((l.strength for l in links), default=0.0)
    story.relevance_score = round(min(1.0, 0.7 * top + 0.05 * min(len(arts), 6) + 0.05 * len(story.topics or [])), 3)
    if not story.content_potential:
        story.content_potential = [{"format": "youtube_short" if len(arts) < 3 else "youtube", "angle": f"Why does the system work this way? — {story.title}", "score": story.relevance_score}]
        story.recommended_format = story.content_potential[0]["format"]
    if story.analysis_source == "none":
        story.analysis_source = "heuristic"


SYSTEM_ANALYSIS = f"""You are a careful, nonpartisan news analyst helping a commentator think.
{INTEGRITY}
Given a cluster of articles about one story and the commentator's principles, produce JSON with keys:
summary (one paragraph, neutral), why_it_matters (one paragraph, tied to systems/incentives),
topics (subset of: {', '.join(TOPIC_LIST)}),
claims (list of {{text, claim_type: FACT|ANALYSIS|OPINION|COUNTERFACTUAL|PREDICTION, supporting_passage (verbatim short quote from the material or empty), source_url}}; extract the major factual assertions and label opinions honestly),
arguments (list of {{side, argument}} — the strongest arguments on at least two sides, steelmanned),
unresolved_questions (list of factual questions that would need verification),
competing_interpretations (list of short strings),
content_potential (list of {{format (one of {', '.join(FORMATS)}), angle, score 0-1}}),
recommended_format (one of the formats),
principle_links (list of {{title (exact principle title from the list), relation: supports|challenges|relates, strength 0-1, note}}).
Be concise. Do not invent facts not present in the material."""


def llm_analysis(db: Session, story: Story, router: Router) -> bool:
    arts = [a for a in story.articles if not a.duplicate_of_id][:8]
    principles = db.execute(select(Principle).where(Principle.status != "retired")).scalars().all()
    material = []
    for a in arts:
        body = (a.content or a.summary or "")[:1500]
        material.append(f"### {a.title}\nPublication: {a.publication} | URL: {a.url} | Published: {a.published_at}\n{body}")
    user = f"STORY: {story.title}\n\nARTICLES:\n" + "\n\n".join(material) + "\n\nPRINCIPLES:\n" + principles_block(principles)
    try:
        data, res = chat_json(router, "FAST", "story_analysis", SYSTEM_ANALYSIS, user, max_tokens=2500)
    except (ProviderError, ValueError) as e:
        log.warning("LLM analysis failed for story %s: %s", story.id, e)
        story.analysis_source = "heuristic"
        return False
    story.summary = as_str(data.get("summary")) or story.summary
    story.why_it_matters = as_str(data.get("why_it_matters"))
    topics = normalize_topics(as_list(data.get("topics")))
    story.topics = topics or story.topics
    story.arguments = [a for a in as_list(data.get("arguments")) if isinstance(a, dict)]
    story.unresolved_questions = [as_str(q) for q in as_list(data.get("unresolved_questions"))]
    story.competing_interpretations = [as_str(q) for q in as_list(data.get("competing_interpretations"))]
    cp = [c for c in as_list(data.get("content_potential")) if isinstance(c, dict)]
    if cp:
        story.content_potential = cp
    rf = as_str(data.get("recommended_format"))
    story.recommended_format = rf if rf in FORMATS else (cp[0].get("format") if cp else story.recommended_format)
    # claims
    db.query(Claim).filter(Claim.story_id == story.id).delete()
    by_url = {a.url: a for a in arts}
    for c in as_list(data.get("claims")):
        if not isinstance(c, dict) or not c.get("text"):
            continue
        ctype = str(c.get("claim_type", "FACT")).upper()
        src = by_url.get(c.get("source_url") or "")
        db.add(
            Claim(
                story_id=story.id,
                article_id=src.id if src else (arts[0].id if arts else None),
                text=as_str(c["text"])[:2000],
                claim_type=ctype if ctype in CLAIM_TYPES else "ANALYSIS",
                supporting_passage=as_str(c.get("supporting_passage"))[:1000],
                source_url=as_str(c.get("source_url")) or (src.url if src else (arts[0].url if arts else "")),
                publication=src.publication if src else (arts[0].publication if arts else ""),
                is_primary_source=bool(src and src.source and src.source.is_primary),
                verification_status="UNVERIFIED" if ctype == "FACT" else "N/A",
            )
        )
    # principle links from the model (merge with heuristic links)
    by_title = {p.title.lower(): p for p in principles}
    existing = {l.principle_id: l for l in story.principle_links}
    for pl in as_list(data.get("principle_links")):
        if not isinstance(pl, dict):
            continue
        p = by_title.get(as_str(pl.get("title")).lower())
        if p is None:
            continue
        rel = as_str(pl.get("relation")).lower()
        rel = rel if rel in {"supports", "challenges", "relates"} else "relates"
        try:
            strength = float(pl.get("strength", 0.5))
        except (TypeError, ValueError):
            strength = 0.5
        link = existing.get(p.id)
        if link is None:
            link = StoryPrincipleLink(story_id=story.id, principle_id=p.id)
            db.add(link)
            existing[p.id] = link
        link.relation = rel
        link.strength = round(max(link.strength or 0, min(1.0, strength)), 3)
        link.note = as_str(pl.get("note"))[:500]
    db.flush()
    top = max((l.strength for l in existing.values()), default=0.0)
    challenge_bonus = 0.1 if any(l.relation == "challenges" for l in existing.values()) else 0.0
    story.relevance_score = round(min(1.0, 0.65 * top + challenge_bonus + 0.05 * min(len(arts), 5)), 3)
    story.analysis_source = f"llm:{res.model}"
    return True


def analyze_story(db: Session, story: Story, *, router: Router | None = None, use_llm: bool = True) -> Story:
    router = router or Router(db)
    heuristic_analysis(db, story, router)
    used_llm = False
    if use_llm:
        used_llm = llm_analysis(db, story, router)
    story.analysis_version = (story.analysis_version or 0) + 1
    story.analyzed_at = datetime.now(timezone.utc)
    if story.status == "new":
        story.status = "developing"
    db.add(StoryEvent(story_id=story.id, occurred_at=story.analyzed_at, kind="analysis", description=f"Analysed ({'local model' if used_llm else 'heuristic'}); relevance {story.relevance_score:.2f}"))
    db.commit()
    embed_entity(db, "story", story, router)
    for a in story.articles:
        if not a.duplicate_of_id:
            embed_entity(db, "article", a, router)
    return story


def analyze_pending_stories(db: Session, *, limit: int = 60, progress=None) -> int:
    router = Router(db)
    rows = db.execute(select(Story).where(Story.status != "ignored")).scalars().all()
    pending = [s for s in rows if s.analyzed_at is None or s.last_updated > s.analyzed_at]
    pending.sort(key=lambda s: s.last_updated, reverse=True)
    n = 0
    for i, s in enumerate(pending[:limit]):
        if progress:
            progress(0.9 + 0.1 * i / max(1, len(pending)), f"Analysing {s.title[:60]}")
        try:
            analyze_story(db, s, router=router)
            n += 1
        except Exception as e:  # keep going; never let one story break the batch
            log.exception("analysis failed for %s: %s", s.id, e)
            db.rollback()
    return n
