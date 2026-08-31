"""Faceless Content Studio: generation of scripted videos and carousels.

The user picks a source and (optionally) a style + length; everything else is inferred and
editable afterwards. Scenes follow the VideoScene schema (see models.VideoProject docstring).
Rendering lives in `services/render_video.py`.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    FACELESS_FORMATS,
    SCENE_VISUAL_TYPES,
    Claim,
    ContentItem,
    PositionBrief,
    Principle,
    ResearchNote,
    Story,
    Video,
    VideoProject,
)
from ..providers.base import ProviderError
from ..providers.registry import Router
from ..providers.tts.local import WORDS_PER_SECOND
from .design import role_for
from .llm_utils import as_list, as_str, chat_json
from .search import embed_entity
from .voice import INTEGRITY, VOICE

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Format specs (structure the model must follow)
# ---------------------------------------------------------------------------
FORMAT_SPECS: dict[str, dict[str, Any]] = {
    "question": {
        "label": "Question",
        "default_seconds": 20,
        "pattern": "1) A bold question as a title scene. 2) One or two short framing scenes that sharpen the tension (e.g. 'If every citizen receives one vote…' → '…should one citizen be able to spend $100 million influencing an election?'). 3) Closing scene: 'What do you think?'",
        "scene_range": (3, 5),
    },
    "text_explainer": {
        "label": "Text explainer",
        "default_seconds": 45,
        "pattern": "1) Hook question/statement. 2) Simple explanation across 2-4 scenes (short sentences, one idea per scene; use a chart or comparison where a number matters). 3) Ending question inviting discussion.",
        "scene_range": (4, 8),
    },
    "news_explainer": {
        "label": "News explainer",
        "default_seconds": 45,
        "pattern": "1) 'WHAT JUST HAPPENED?' title with the story headline. 2) The 3 most important facts, one scene each (each with its source). 3) Why it matters. 4) What both sides argue (one scene per side, steelmanned). 5) Question for the viewer.",
        "scene_range": (6, 9),
    },
    "did_you_know": {
        "label": "Did you know?",
        "default_seconds": 20,
        "pattern": "1) 'DID YOU KNOW?' title. 2) The fact (with source). 3) One scene of context. 4) Why it matters. 5) Question.",
        "scene_range": (4, 5),
    },
    "system_explainer": {
        "label": "How the system works",
        "default_seconds": 60,
        "pattern": "1) 'WHY DOES … WORK THIS WAY?' question. 2) HOW IT WORKS (1-2 scenes, use comparison/timeline visuals). 3) WHY IT EXISTS (history/incentive). 4) WHERE THE INCENTIVE BREAKS. 5) POSSIBLE FIX. 6) 'What do you think?'",
        "scene_range": (6, 9),
    },
    "data_story": {
        "label": "Data story",
        "default_seconds": 30,
        "pattern": "1) The NUMBER, huge, as a counter visual (with source). 2) A COMPARISON that makes it tangible (comparison or chart visual). 3) CONTEXT. 4) WHY IT MATTERS. 5) Question. Every statistic must carry its source; if the material has no reliable number, say so instead of inventing one.",
        "scene_range": (4, 6),
    },
    "argument": {
        "label": "Both sides",
        "default_seconds": 30,
        "pattern": "1) The issue as a title. 2) 'THE ARGUMENT FOR' — the strongest steelmanned argument (paraphrased position, never a fabricated quotation). 3) 'THE ARGUMENT AGAINST' — same rigor. 4) 'Where should the line be?' closing question. Label arguments as arguments, not as quotes from real people.",
        "scene_range": (4, 6),
    },
    "my_take": {
        "label": "My take",
        "default_seconds": 45,
        "pattern": "1) 'MY TAKE' + the issue. 2) The position in one clear sentence. 3-4) The reasoning in 2-3 concise scenes (acknowledge the strongest counterargument in one of them). 5) Closing question inviting disagreement.",
        "scene_range": (4, 6),
    },
    "custom": {
        "label": "Custom",
        "default_seconds": 30,
        "pattern": "Use the structure that best fits the idea: hook, 2-4 substance scenes, closing question.",
        "scene_range": (3, 8),
    },
}

DEFAULT_FORMAT_BY_SOURCE = {"story": "news_explainer", "brief": "my_take", "principle": "question", "research_note": "text_explainer", "custom": "question"}
PLATFORM_LIMITS = {"tiktok": 600, "instagram_reel": 90, "youtube_short": 180, "facebook_reel": 90, "x": 140}
BACKGROUNDS = ["auto", "primary", "background", "accent", "gradient"]
ANIMATIONS = ["fade", "slide_up", "pop", "typewriter", "none"]

SYSTEM_SCENES = f"""{VOICE}
{INTEGRITY}
You write short faceless vertical videos (1080x1920, animated text on clean brand backgrounds — no
footage, no faces). Return JSON:
{{"title": "video title (≤70 chars, honest, no clickbait)",
 "caption": "platform caption ≤200 chars ending with an invitation to comment",
 "hashtags": ["3-6 relevant tags without #"],
 "music_recommendation": "one line describing the mood/genre of background music to look for",
 "sources": [{{"label": "publication or dataset", "url": "https://..."}}] (only sources actually present in the material; empty list if none),
 "scenes": [{{
   "duration": seconds (number; scenes are 1.5-8s; total must be close to the target length),
   "narration": "what a voiceover would say for this scene (natural spoken language; empty string if the on-screen text carries it)",
   "on_screen_text": "the BIG text on screen. ≤12 words. ALL-CAPS only for title/question scenes.",
   "subtext": "optional smaller supporting line, ≤14 words, or empty",
   "visual_type": one of {SCENE_VISUAL_TYPES},
   "visual": for chart: {{"labels": [..], "values": [..], "unit": "", "title": "", "source": "publication"}};
             for counter: {{"from": 0, "to": number, "prefix": "", "suffix": "", "label": ""}};
             for comparison: {{"left": {{"label": "", "value": ""}}, "right": {{"label": "", "value": ""}}}};
             for timeline: {{"points": [{{"label": "", "text": ""}}]}};
             for list: {{"items": ["...", "..."]}};
             otherwise {{}},
   "animation": one of {ANIMATIONS},
   "transition": "cut" or "fade",
   "background": one of {BACKGROUNDS},
   "emphasis": ["words", "from the on_screen_text to highlight"] (0-3 words),
   "source": "attribution for any factual claim in this scene (publication name), or empty"
 }}]}}
Rules: narration must be speakable within the scene duration (~{WORDS_PER_SECOND} words/second).
Never fabricate quotations, numbers or events; if the material lacks a number, do not invent one.
One idea per scene. The last scene asks the viewer a real question.
Vary the scenes: a deck where every scene is plain text is a failure. Whenever the material
supports it use counter (a single figure), comparison (two values against each other), chart,
timeline or list — but only with numbers that appear in the material."""


# ---------------------------------------------------------------------------
# Source material
# ---------------------------------------------------------------------------
def resolve_source(db: Session, src: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Returns (source_kind, material_text, link_fields_for_content_item)."""
    if src.get("story_id"):
        story = db.get(Story, src["story_id"])
        if story is None:
            raise ValueError("story not found")
        claims = db.query(Claim).filter(Claim.story_id == story.id).limit(12).all()
        arts = [a for a in story.articles if not a.duplicate_of_id][:6]
        material = f"STORY: {story.title}\nSummary: {story.summary}\nWhy it matters: {story.why_it_matters}\n"
        if claims:
            material += "CLAIMS:\n" + "\n".join(f"- [{c.claim_type}] {c.text} (source: {c.publication} {c.source_url})" for c in claims) + "\n"
        if story.arguments:
            material += "ARGUMENTS:\n" + "\n".join(f"- ({a.get('side')}) {a.get('argument')}" for a in story.arguments if isinstance(a, dict)) + "\n"
        material += "SOURCES:\n" + "\n".join(f"- {a.publication}: {a.title} — {a.url}" for a in arts)
        return "story", material, {"story_id": story.id}
    if src.get("brief_id"):
        b = db.get(PositionBrief, src["brief_id"])
        if b is None:
            raise ValueError("position not found")
        material = (
            f"MY POSITION on {b.issue}: {b.position}\nRationale: {b.rationale}\n"
            f"Strongest counterargument: {b.strongest_against}\nMy response: {b.response}\n"
            f"Assumptions: {b.factual_assumptions}\nMechanisms: {b.policy_mechanisms}"
        )
        return "brief", material, {"position_brief_id": b.id, "story_id": b.story_id, "principle_ids": [b.governing_principle_id] if b.governing_principle_id else []}
    if src.get("principle_id"):
        p = db.get(Principle, src["principle_id"])
        if p is None:
            raise ValueError("belief not found")
        counters = "\n".join(f"- {c.argument}" for c in p.counterarguments[:3])
        material = f"MY BELIEF ({p.category}): {p.title}\nPosition: {p.current_position}\nRationale: {p.rationale}\nCounterarguments I take seriously:\n{counters}"
        return "principle", material, {"principle_ids": [p.id]}
    if src.get("research_note_id"):
        n = db.get(ResearchNote, src["research_note_id"])
        if n is None:
            raise ValueError("research note not found")
        return "research_note", f"RESEARCH: {n.title}\n{n.body}", {"story_id": n.story_id, "principle_ids": [n.principle_id] if n.principle_id else []}
    if src.get("video_id"):
        v = db.get(Video, src["video_id"])
        if v is None:
            raise ValueError("video not found")
        text = " ".join(s.text for s in v.segments)[:6000]
        return "video", f"MY RECORDING ({v.filename}): {v.summary}\nTRANSCRIPT EXCERPT:\n{text}", {"source_video_id": v.id}
    idea = as_str(src.get("idea") or src.get("custom_idea"))
    if not idea:
        raise ValueError("provide a source (story/position/belief/research/video) or an idea")
    return "custom", f"IDEA: {idea}", {}


# ---------------------------------------------------------------------------
# Scene normalisation
# ---------------------------------------------------------------------------
_NUMBER = re.compile(r"(?P<prefix>[$€£]?)(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix>%|percent|bn|billion|m|million|k|thousand|x|times)?", re.I)
_SCALE = {"bn": 1e9, "billion": 1e9, "m": 1e6, "million": 1e6, "k": 1e3, "thousand": 1e3}


def _promote_number(scene: dict[str, Any]) -> None:
    """A slide whose whole point is a figure should show the figure. Only ever promotes a
    number that is already in the copy — it never invents one."""
    if scene["visual_type"] not in ("text", "title") or scene.get("visual"):
        return
    for field in ("on_screen_text", "subtext"):
        m = _NUMBER.search(scene[field] or "")
        if not m:
            continue
        try:
            value = float(m.group("num").replace(",", ""))
        except ValueError:
            continue
        suffix_raw = (m.group("suffix") or "").lower()
        if suffix_raw in _SCALE:
            value *= _SCALE[suffix_raw]
            suffix = ""
        elif suffix_raw in ("%", "percent"):
            suffix = "%"
        elif suffix_raw in ("x", "times"):
            suffix = "x"
        else:
            suffix = ""
        if value < 10 and not suffix:  # "3 things to watch" is not a statistic
            return
        rest = (scene["subtext"] if field == "on_screen_text" else scene["on_screen_text"]) or ""
        scene["visual_type"] = "counter"
        label = re.sub(r"\s{2,}", " ", (scene[field][: m.start()] + scene[field][m.end() :])).strip(" ,.—-")
        scene["visual"] = {"from": 0, "to": value, "prefix": m.group("prefix") or "", "suffix": suffix, "label": label[:60]}
        if field == "on_screen_text" and rest:
            scene["on_screen_text"] = rest[:140]
            scene["subtext"] = ""
        return


def _auto_emphasis(scene: dict[str, Any]) -> None:
    """Highlight the figure in a line, and nothing else. Gilding an arbitrary long word
    looks like a mistake — emphasis has to mean something."""
    if scene.get("emphasis"):
        return
    numeric = [w for w in re.findall(r"[\w$%,.'’-]+", scene.get("on_screen_text") or "") if any(c.isdigit() for c in w)]
    if numeric:
        scene["emphasis"] = [numeric[0]]


def _apply_design(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn a flat list of text slides into a designed sequence: a role per scene, figures
    promoted into stat cards, one emphasized term per line, surfaces left to the deck rhythm."""
    total = len(scenes)
    for i, s in enumerate(scenes):
        _promote_number(s)
        _auto_emphasis(s)
        s["role"] = role_for(s, i, total)
        if s["role"] in ("cover", "question", "closer") and s["visual_type"] == "text":
            s["visual_type"] = {"cover": "title", "question": "question", "closer": "text"}[s["role"]]
    return scenes


def normalize_scenes(raw: list[Any], *, target_seconds: int) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        text = as_str(s.get("on_screen_text")).strip()
        narration = as_str(s.get("narration")).strip()
        if not text and not narration:
            continue
        try:
            dur = float(s.get("duration", 3))
        except (TypeError, ValueError):
            dur = 3.0
        vt = as_str(s.get("visual_type")) or "text"
        if vt not in SCENE_VISUAL_TYPES:
            vt = "text"
        anim = as_str(s.get("animation")) or "fade"
        if anim not in ANIMATIONS:
            anim = "fade"
        # A model choosing a surface can't see the rest of the deck, so its pick is only
        # honoured once a person has locked it in the editor.
        bg = as_str(s.get("background")) or "auto"
        if bg not in BACKGROUNDS:
            bg = "auto"
        locked = bool(s.get("surface_locked")) and bg != "auto"
        # narration must fit: extend duration if needed
        if narration:
            need = len(narration.split()) / WORDS_PER_SECOND + 0.4
            dur = max(dur, need)
        dur = max(1.5, min(10.0, dur))
        scenes.append(
            {
                "order": len(scenes),
                "duration": round(dur, 2),
                "narration": narration,
                "on_screen_text": text[:140],
                "subtext": as_str(s.get("subtext"))[:120],
                "visual_type": vt,
                "visual": s.get("visual") if isinstance(s.get("visual"), dict) else {},
                "animation": anim,
                "transition": "fade" if as_str(s.get("transition")) == "fade" else "cut",
                "background": bg,
                "surface_locked": locked,
                "role": as_str(s.get("role")),
                "kicker": as_str(s.get("kicker"))[:40],
                "emphasis": [as_str(w) for w in as_list(s.get("emphasis"))][:3],
                "source": as_str(s.get("source"))[:200],
            }
        )
    if not scenes:
        raise ProviderError("model returned no usable scenes", provider="faceless")
    scenes = _apply_design(scenes)
    # scale toward target length (never squeezing narration out of its scene)
    total = sum(s["duration"] for s in scenes)
    if total > 0 and abs(total - target_seconds) / max(target_seconds, 1) > 0.25:
        factor = target_seconds / total
        for s in scenes:
            floor = (len(s["narration"].split()) / WORDS_PER_SECOND + 0.4) if s["narration"] else 1.5
            s["duration"] = round(max(floor, min(10.0, s["duration"] * factor)), 2)
    return scenes


def total_duration(scenes: list[dict[str, Any]]) -> float:
    return round(sum(float(s.get("duration", 0)) for s in scenes), 2)


# ---------------------------------------------------------------------------
# Project creation & generation
# ---------------------------------------------------------------------------
def create_project(
    db: Session,
    *,
    source: dict[str, Any],
    kind: str = "faceless_video",
    fmt: str | None = None,
    target_seconds: int | None = None,
    platform: str | None = None,
    voice_mode: str | None = None,
    title: str | None = None,
) -> VideoProject:
    source_kind, material, links = resolve_source(db, source)
    fmt = fmt or DEFAULT_FORMAT_BY_SOURCE.get(source_kind, "question")
    if fmt not in FACELESS_FORMATS:
        raise ValueError(f"unknown format {fmt}")
    spec = FORMAT_SPECS[fmt]
    seconds = int(target_seconds or spec["default_seconds"])
    item = ContentItem(
        title=(title or f"{spec['label']} draft")[:400],
        format="youtube_short" if kind == "faceless_video" else "infographic",
        status="SCRIPTING",
        platform=platform or ("youtube_short" if kind == "faceless_video" else "instagram_post"),
        **{k: v for k, v in links.items() if v},
    )
    db.add(item)
    db.flush()
    project = VideoProject(
        content_item_id=item.id,
        kind=kind,
        format=fmt,
        target_seconds=seconds,
        platform=item.platform,
        voice_mode=voice_mode or "none",
        generation_meta={"source_kind": source_kind, "source": {k: v for k, v in source.items() if v}, "material_chars": len(material)},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def generate_scenes(db: Session, project: VideoProject, *, router: Router | None = None, extra_instructions: str = "") -> VideoProject:
    router = router or Router(db)
    spec = FORMAT_SPECS[project.format]
    source_kind = (project.generation_meta or {}).get("source_kind", "custom")
    _, material, _ = resolve_source(db, (project.generation_meta or {}).get("source", {}))
    lo, hi = spec["scene_range"]
    user = (
        f"FORMAT: {spec['label']}\nSTRUCTURE: {spec['pattern']}\n"
        f"TARGET LENGTH: {project.target_seconds} seconds total, {lo}-{hi} scenes.\nPLATFORM: {project.platform}\n"
        + (f"ADDITIONAL DIRECTION: {extra_instructions}\n" if extra_instructions else "")
        + f"\nMATERIAL:\n{material}"
    )
    data, res = chat_json(router, "WRITING", "faceless", SYSTEM_SCENES, user, temperature=0.6, max_tokens=3500)
    scenes = normalize_scenes(as_list(data.get("scenes")), target_seconds=project.target_seconds)
    project.previous_scenes = project.scenes or []
    project.scenes = scenes
    project.caption = as_str(data.get("caption"))[:500]
    project.hashtags = [as_str(h).lstrip("#") for h in as_list(data.get("hashtags"))][:8]
    project.music_recommendation = as_str(data.get("music_recommendation"))[:300]
    srcs = [s for s in as_list(data.get("sources")) if isinstance(s, dict) and s.get("label")]
    project.sources = [{"label": as_str(s.get("label"))[:120], "url": as_str(s.get("url"))[:500]} for s in srcs][:10]
    meta = dict(project.generation_meta or {})
    meta.update({"model": res.model, "provider": res.provider, "source_kind": source_kind})
    project.generation_meta = meta
    item = project.content_item
    new_title = as_str(data.get("title"))
    if new_title and (item.title.endswith("draft") or not item.title):
        item.title = new_title[:400]
    item.script = "\n".join(f"[{s['duration']}s] {s['on_screen_text']}" + (f" — VO: {s['narration']}" if s["narration"] else "") for s in scenes)
    pkg = dict(item.package or {})
    pkg["faceless_project_id"] = project.id
    item.package = pkg
    db.commit()
    embed_entity(db, "content_item", item, router)
    return project


VARIATIONS = {
    "shorter": "Cut the total length by ~40%. Remove the weakest scenes, tighten every line.",
    "more_direct": "Make it more direct: shorter sentences, active voice, no hedging (keep honest uncertainty where facts are unsettled).",
    "more_curious": "Reframe around curiosity: lead with questions, withhold the answer until later scenes.",
    "more_educational": "Add one concrete explanatory scene (chart, comparison, or timeline) and define any term a newcomer wouldn't know.",
    "more_humorous": "Add light observational or system-absurdity humor. No rage bait, no cheap insults, no partisan digs.",
    "more_serious": "Remove humor and softeners; measured, sober tone.",
    "simpler": "Explain it so a smart 15-year-old gets it. One idea per scene, shorter words.",
    "stronger_hook": "Rewrite the first scene to stop the scroll in 1.5 seconds — a sharper question or a startling (true, sourced) fact.",
    "change_visual_style": "Vary backgrounds and visual types across scenes (use at least one chart/comparison/counter where a number appears), and change up the animations.",
}


def apply_variation(db: Session, project: VideoProject, variation: str, *, router: Router | None = None) -> VideoProject:
    if variation not in VARIATIONS:
        raise ValueError(f"unknown variation {variation}")
    router = router or Router(db)
    import json as _json

    user = (
        f"Here is the current scene list for a {FORMAT_SPECS[project.format]['label']} video "
        f"(target {project.target_seconds}s):\n{_json.dumps(project.scenes, indent=1)}\n\n"
        f"REVISION INSTRUCTION: {VARIATIONS[variation]}\n"
        "Return the full JSON object again (title/caption/hashtags/music_recommendation/sources/scenes) with the revised scenes."
    )
    data, res = chat_json(router, "WRITING", "faceless", SYSTEM_SCENES, user, temperature=0.6, max_tokens=3500)
    target = int(project.target_seconds * 0.6) if variation == "shorter" else project.target_seconds
    scenes = normalize_scenes(as_list(data.get("scenes")), target_seconds=target)
    project.previous_scenes = project.scenes or []
    project.scenes = scenes
    if variation == "shorter":
        project.target_seconds = target
    if as_str(data.get("caption")):
        project.caption = as_str(data.get("caption"))[:500]
    meta = dict(project.generation_meta or {})
    meta["last_variation"] = variation
    meta["model"] = res.model
    project.generation_meta = meta
    project.render_status = "none"  # scenes changed → previous render is stale
    db.commit()
    return project


def regenerate_scene(db: Session, project: VideoProject, index: int, *, instruction: str = "", router: Router | None = None) -> VideoProject:
    scenes = list(project.scenes or [])
    if not 0 <= index < len(scenes):
        raise ValueError("scene index out of range")
    router = router or Router(db)
    import json as _json

    user = (
        f"Video context (all scenes):\n{_json.dumps(scenes, indent=1)}\n\n"
        f"Rewrite ONLY scene {index} ({_json.dumps(scenes[index])}).\n"
        + (f"Direction: {instruction}\n" if instruction else "Make it clearer and punchier.\n")
        + 'Return JSON: {"scenes": [<the single revised scene object>]}'
    )
    data, _ = chat_json(router, "WRITING", "faceless", SYSTEM_SCENES, user, temperature=0.7, max_tokens=800)
    new = normalize_scenes(as_list(data.get("scenes")), target_seconds=int(scenes[index].get("duration", 3)))
    scenes[index] = {**new[0], "order": index}
    project.previous_scenes = project.scenes or []
    project.scenes = scenes
    project.render_status = "none"
    db.commit()
    return project


def update_scenes(db: Session, project: VideoProject, scenes: list[dict[str, Any]]) -> VideoProject:
    project.previous_scenes = project.scenes or []
    project.scenes = normalize_scenes(scenes, target_seconds=project.target_seconds)
    project.render_status = "none"
    db.commit()
    return project


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------
def quality_checks(db: Session, project: VideoProject) -> list[dict[str, str]]:
    item = project.content_item
    checks: list[dict[str, str]] = []

    unresolved = [c for c in item.fact_check_claims if not c.resolved]
    if item.fact_check_status == "not_run":
        checks.append({"check": "Facts", "status": "warn", "detail": "Fact check hasn't been run yet."})
    elif unresolved:
        checks.append({"check": "Facts", "status": "fail", "detail": f"{len(unresolved)} factual line(s) still unverified."})
    else:
        checks.append({"check": "Facts", "status": "pass", "detail": "All extracted claims resolved." if item.fact_check_claims else "No factual claims flagged."})

    factual_scenes = [s for s in project.scenes or [] if s.get("visual_type") in ("chart", "counter", "comparison", "timeline") or any(ch.isdigit() for ch in s.get("on_screen_text", ""))]
    missing_src = [s for s in factual_scenes if not s.get("source") and not (s.get("visual") or {}).get("source")]
    if factual_scenes and not project.sources and missing_src:
        checks.append({"check": "Sources", "status": "fail", "detail": "Scenes show numbers but no source is attached."})
    elif missing_src:
        checks.append({"check": "Sources", "status": "warn", "detail": f"{len(missing_src)} data scene(s) lack a per-scene source (project sources exist)."})
    else:
        checks.append({"check": "Sources", "status": "pass", "detail": f"{len(project.sources or [])} source(s) attached."})

    wordy = [s for s in project.scenes or [] if len((s.get("on_screen_text") or "").split()) > 14]
    checks.append(
        {"check": "Clarity", "status": "warn" if wordy else "pass", "detail": f"{len(wordy)} scene(s) exceed 14 on-screen words." if wordy else "Scene text within limits."}
    )

    dur = total_duration(project.scenes or [])
    limit = PLATFORM_LIMITS.get(project.platform, 180)
    if dur == 0:
        checks.append({"check": "Length", "status": "fail", "detail": "No scenes yet."})
    elif dur > limit:
        checks.append({"check": "Length", "status": "fail", "detail": f"{dur:.0f}s exceeds the {limit}s limit for {project.platform}."})
    else:
        checks.append({"check": "Length", "status": "pass", "detail": f"{dur:.0f}s (limit {limit}s)."})

    checks.append({"check": "Platform fit", "status": "pass", "detail": "1080×1920 vertical with safe-zone margins."})

    imgs = [s for s in project.scenes or [] if s.get("visual_type") == "image"]
    unattributed = [s for s in imgs if not (s.get("visual") or {}).get("source_label") and not (s.get("visual") or {}).get("generated") and not (s.get("visual") or {}).get("uploaded")]
    if unattributed:
        checks.append({"check": "Asset provenance", "status": "fail", "detail": f"{len(unattributed)} image(s) without provenance (uploaded / generated / attributed)."})
    else:
        checks.append({"check": "Asset provenance", "status": "pass", "detail": "All visuals are brand-rendered, uploaded or attributed."})

    generated = [s for s in imgs if (s.get("visual") or {}).get("generated")]
    if generated:
        checks.append({"check": "AI image disclosure", "status": "warn", "detail": "Contains generated imagery — the render labels it; keep the label."})
    else:
        checks.append({"check": "AI image disclosure", "status": "pass", "detail": "No generated imagery."})

    checks.append(
        {"check": "Human approval", "status": "pass" if item.approved_at else "warn", "detail": "Approved." if item.approved_at else "Not approved yet — nothing publishes automatically."}
    )
    return checks


# ---------------------------------------------------------------------------
# Carousel generation (slides reuse the scene schema: heading→on_screen_text, body→subtext)
# ---------------------------------------------------------------------------
SYSTEM_CAROUSEL = f"""{VOICE}
{INTEGRITY}
You write Instagram/LinkedIn carousels (1080x1350 slides, brand backgrounds, no photos needed).
Return JSON: {{"title", "caption" (≤200 chars), "hashtags" (3-6, no #),
"sources": [{{"label", "url"}}] (only sources present in the material),
"slides": [{{"heading": "≤10 words (ALL-CAPS only on the first and last slide)",
"body": "1-3 short sentences, ≤40 words; empty on the title slide",
"footer": "optional small line (e.g. 'Source: …' or 'swipe →'), or empty",
"layout": "title" | "body" | "question"}}]}}
6-8 slides. Slide 1 hooks with the question. Last slide asks the reader a real question.
Never fabricate numbers or quotes; carry sources for every factual claim."""


def generate_carousel_slides(db: Session, project: VideoProject, *, router: Router | None = None, extra_instructions: str = "") -> VideoProject:
    router = router or Router(db)
    _, material, _ = resolve_source(db, (project.generation_meta or {}).get("source", {}))
    user = ("SLIDES: 6-8.\n" + (f"DIRECTION: {extra_instructions}\n" if extra_instructions else "") + f"\nMATERIAL:\n{material}")
    data, res = chat_json(router, "WRITING", "carousel", SYSTEM_CAROUSEL, user, temperature=0.6, max_tokens=2000)
    slides = []
    for s in as_list(data.get("slides")):
        if not isinstance(s, dict) or not as_str(s.get("heading")):
            continue
        layout = as_str(s.get("layout"))
        slides.append(
            {
                "order": len(slides),
                "duration": 0,
                "narration": "",
                "on_screen_text": as_str(s.get("heading"))[:120],
                "subtext": as_str(s.get("body"))[:400],
                "visual_type": "title" if layout == "title" else ("question" if layout == "question" else "text"),
                "visual": {"footer": as_str(s.get("footer"))[:120]} if s.get("footer") and not as_str(s.get("footer")).lower().startswith("source:") else {},
                "animation": "none",
                "transition": "cut",
                "background": "primary" if layout in ("title", "question") else "background",
                "emphasis": [],
                "source": as_str(s.get("footer"))[7:].strip()[:200] if as_str(s.get("footer")).lower().startswith("source:") else "",
            }
        )
    if not slides:
        raise ProviderError("model returned no usable slides", provider="faceless")
    project.previous_scenes = project.scenes or []
    project.scenes = slides
    project.caption = as_str(data.get("caption"))[:500]
    project.hashtags = [as_str(h).lstrip("#") for h in as_list(data.get("hashtags"))][:8]
    project.sources = [{"label": as_str(s.get("label"))[:120], "url": as_str(s.get("url"))[:500]} for s in as_list(data.get("sources")) if isinstance(s, dict) and s.get("label")][:10]
    meta = dict(project.generation_meta or {})
    meta["model"] = res.model
    project.generation_meta = meta
    item = project.content_item
    if as_str(data.get("title")):
        item.title = as_str(data.get("title"))[:400]
    item.script = "\n\n".join(f"[slide {i + 1}] {s['on_screen_text']}\n{s['subtext']}" for i, s in enumerate(slides))
    db.commit()
    embed_entity(db, "content_item", item, router)
    return project
