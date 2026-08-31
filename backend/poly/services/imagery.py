"""Pictures for scenes: where they come from, and what may be said about them.

A slide of pure type is honest but inert. This resolves a scene's *visual intent* into an
actual picture, in a fixed order of preference:

1. a picture already attached to the scene (the owner's choice always wins)
2. an approved image already in the library — no network, no duplicate downloads
3. an openly-licensed photograph (Wikimedia Commons, then Openverse), stored with its
   license and photographer so the slide can credit it
4. an editorial illustration from a local image model, if one is configured
5. a symbolic mark drawn from the brand (services/symbols.py) — always available

Two rules are not configurable:

* Only licenses that permit republication are downloaded. An uncredited picture is not a
  usable picture, so anything without a license and an author is dropped.
* Generated pictures of real people are editorial cartoons — flat, drawn, obviously not
  photographs — and are always labelled as AI-generated on the slide. Poly will not make a
  photorealistic image of a real person, because a labelled photoreal fake still travels as
  evidence once it leaves the app.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import httpx
from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Article, Image, VideoProject
from ..providers.base import ImageCandidate, PrivacyViolation, ProviderError
from ..providers.image.local_generative import LocalGenerativeImageProvider
from ..providers.image_search import all_providers
from .privacy import NetworkPolicy
from .subjects import Subject, extract, for_scene, frame_for, score_candidate, thing_in
from .symbols import SYMBOLS

log = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024
MAX_EDGE = 2400
TREATMENTS = ["full_bleed", "band", "portrait"]
# Bumped whenever picture selection itself gets better. A picture Poly chose under older,
# worse rules is re-picked on the next run; one the owner pinned is never touched. Without
# this, an improvement only reaches new decks and every existing slide keeps its bad guess.
PICKER_VERSION = 2

# Words that would push a generator toward a photograph. Stripped from every prompt.
_PHOTOREAL = re.compile(r"\b(photo\w*|photograph\w*|realistic|hyper[- ]?real\w*|lifelike|4k|8k|dslr|render(ing)?|cgi|deep\s*fake|deepfake)\b", re.I)
_STOP = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "from", "that", "this", "it", "is", "are", "was", "were", "be", "been", "has", "have", "had", "his", "her", "their", "its", "not", "what", "why", "how", "does", "did", "who", "will", "would", "should", "could", "than", "then", "when", "about", "over", "under", "after", "before", "more", "most", "less", "says", "said"}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def search(db: Session, query: str, *, limit: int = 12, subject: Subject | None = None, thing: str = "") -> list[dict[str, Any]]:
    """Openly-licensed pictures for a query, best first.

    With a `subject`, results that do not actually depict it are dropped rather than ranked
    down. A picture archive's full-text index associates a name with everything ever written
    about it, so "Trump focus" returns a historian who writes about him. A wrong picture is
    worse than none: the reader believes it.
    """
    policy = NetworkPolicy.load(db)
    policy.check(locality="cloud", purpose="research", provider="image_search")
    out: list[dict[str, Any]] = []
    errors: list[str] = []
    for provider in all_providers():
        if len(out) >= limit:
            break
        try:
            for c in provider.search(query, limit=limit - len(out)):
                if c.url:
                    out.append(_as_dict(c))
        except ProviderError as e:
            errors.append(str(e))
            log.warning("image search via %s failed: %s", provider.name, e)
    if subject is not None:
        scored = [(score_candidate(c["title"], subject, thing=thing), c) for c in out]
        kept = [(s, c) for s, c in scored if s > 0]
        kept.sort(key=lambda pair: -pair[0])
        for s, c in kept:
            c["match_score"] = s
        rejected = len(out) - len(kept)
        if rejected:
            log.info("dropped %d picture(s) that do not depict %s", rejected, subject.name)
        out = [c for _, c in kept]
    if not out and errors:
        raise ProviderError("; ".join(errors[:2]), provider="image_search")
    return out


def _as_dict(c: ImageCandidate) -> dict[str, Any]:
    return {
        "url": c.url, "thumb_url": c.thumb_url, "title": c.title, "source_page": c.source_page,
        "license": c.license, "license_url": c.license_url, "author": c.author,
        "width": c.width, "height": c.height, "provider": c.provider, "credit": c.credit,
    }


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def fetch(db: Session, candidate: dict[str, Any], *, content_item_id: str | None = None) -> Image:
    """Download one licensed picture into the image library, provenance attached."""
    if not candidate.get("license"):
        raise ValueError("refusing to store a picture with no license")
    policy = NetworkPolicy.load(db)
    policy.check(locality="cloud", purpose="research", provider="image_search")
    url = str(candidate["url"])
    with httpx.stream("GET", url, timeout=45, follow_redirects=True, headers={"User-Agent": "Poly/0.1 (personal research tool)"}) as r:
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if not ctype.startswith("image/"):
            raise ValueError(f"not an image ({ctype or 'unknown type'})")
        data = b""
        for chunk in r.iter_bytes():
            data += chunk
            if len(data) > MAX_BYTES:
                raise ValueError("image too large")

    cfg = get_settings()
    cfg.images_path.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^a-z0-9]+", "-", str(candidate.get("title") or "picture").lower()).strip("-")[:60] or "picture"
    path = cfg.images_path / f"src-{stem}-{abs(hash(url)) % 10**8:08d}.jpg"
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    try:
        with PILImage.open(tmp) as im:
            im = im.convert("RGB")
            if max(im.size) > MAX_EDGE:
                im.thumbnail((MAX_EDGE, MAX_EDGE), PILImage.LANCZOS)
            im.save(path, "JPEG", quality=90)
            w, h = im.size
    finally:
        tmp.unlink(missing_ok=True)

    row = Image(
        kind="sourced_photo",
        title=str(candidate.get("title") or "")[:300],
        provider=str(candidate.get("provider") or "image_search"),
        params={k: candidate.get(k) for k in ("license", "license_url", "author", "source_page", "url", "provider")},
        path=str(path), width=w, height=h, is_generated=False, label="photo",
        content_item_id=content_item_id,
    )
    db.add(row)
    db.commit()
    return row


def credit_line(row: Image) -> str:
    p = row.params or {}
    bits = [str(p.get("author") or "").strip(), str(p.get("license") or "").strip()]
    return " · ".join(b for b in bits if b)[:120]


# ---------------------------------------------------------------------------
# Editorial illustration (local model only)
# ---------------------------------------------------------------------------
CARTOON_STYLE = (
    "editorial political cartoon, bold ink linework, flat limited colour, heavy crosshatching, "
    "exaggerated caricature in the style of a newspaper opinion page, clearly a hand-drawn illustration"
)
NEGATIVE = "photograph, photorealistic, realistic skin, camera, lens, 3d render, text, caption, logo, watermark, signature"


def illustration_prompt(subject: str, mood: str = "") -> str:
    """Build a prompt that can only produce a drawing.

    The photoreal vocabulary is stripped rather than balanced against — a prompt that asks for
    both a caricature and a photograph resolves toward the photograph often enough to matter,
    and a photoreal image of a real person is the one thing this must not make.
    """
    subject = _PHOTOREAL.sub("", subject or "").strip(" ,.")
    mood = _PHOTOREAL.sub("", mood or "").strip(" ,.")
    parts = [CARTOON_STYLE, subject]
    if mood:
        parts.append(f"mood: {mood}")
    parts.append("no lettering of any kind")
    return ". ".join(p for p in parts if p)


def generate_illustration(db: Session, subject: str, *, mood: str = "", content_item_id: str | None = None, width: int = 1024, height: int = 1024) -> Image | None:
    """Draw an editorial cartoon with the local image model. Returns None if none is configured."""
    provider = LocalGenerativeImageProvider()
    if not provider.available():
        return None
    NetworkPolicy.load(db).check(locality=provider.locality, purpose="ai", provider=provider.name)
    prompt = illustration_prompt(subject, mood)
    cfg = get_settings()
    cfg.images_path.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:50] or "illustration"
    out = cfg.images_path / f"cartoon-{stem}-{abs(hash(prompt)) % 10**8:08d}.png"
    try:
        res = provider.generate(prompt, out_path=str(out), width=width, height=height, negative_prompt=NEGATIVE)
    except (ProviderError, PrivacyViolation) as e:
        log.warning("illustration generation failed: %s", e)
        return None
    row = Image(
        kind="editorial_cartoon", title=subject[:300], prompt=prompt, provider=res.provider,
        params={"model": res.model, "negative_prompt": NEGATIVE, "mood": mood},
        path=res.path, width=res.width, height=res.height, is_generated=True, label="illustration",
        content_item_id=content_item_id,
    )
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------------------
# Choosing what a scene should show
# ---------------------------------------------------------------------------
_RENAME = re.compile(r"renam\w+|rename[sd]?\b", re.I)
_SIGNED = re.compile(r"\bexecutive order\b|\bsigns?\b|\bsigned\b|\bdecree\b", re.I)
_NAMED_AFTER = re.compile(r"named? (it |them )?after|his name on|puts? his name", re.I)
_QUOTED = re.compile(r"[“\"']([^”\"']{3,60})[”\"']")


def _subject_query(scene: dict[str, Any], cast: list[Subject] | None) -> tuple[str, Subject | None, str]:
    """(search, subject, concrete object) for one scene — a real name, never slide words."""
    headline = str(scene.get("on_screen_text") or "")
    text = ". ".join(x for x in (headline, str(scene.get("subtext") or ""), str(scene.get("narration") or "")) if x)
    # What the headline names outranks what the supporting line merely mentions.
    named_in_headline = [s for s in (cast or []) if s.mentioned_in(headline)]
    subject = for_scene(headline, named_in_headline) if named_in_headline else for_scene(text, cast or [])
    if subject is None:
        return "", None, ""
    thing = thing_in(text)
    return subject.query(frame_for(text), thing), subject, thing


def keywords(text: str, limit: int = 6) -> str:
    words = re.findall(r"[A-Za-z][\w'-]+", text or "")
    keep = [w for w in words if w.lower() not in _STOP and len(w) > 2]
    proper = [w for w in keep if w[0].isupper()]
    picked = (proper or keep)[:limit]
    return " ".join(picked)


def infer_symbol(scene: dict[str, Any], context: str = "") -> dict[str, Any] | None:
    """Propose a mark from the scene's own words.

    The trigger must come from the scene itself — the surrounding story is only allowed to
    fill in details it left out. Reading the trigger from the story stamps every slide in a
    deck with the same mark, which is worse than no mark at all.
    """
    text = f"{scene.get('on_screen_text', '')} {scene.get('subtext', '')} {scene.get('narration', '')}"
    detail = f"{text} {context}"  # details only
    if _RENAME.search(text):
        m = re.search(r"renam\w+\s+(?:the\s+)?([A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,3})\s+(?:to|as)\s+[“\"']?([^”\"'.,]{3,40})", detail)
        if m:
            return {"symbol": "rename", "old": m.group(1).strip()[:40], "new": m.group(2).strip().upper()[:40]}
        quoted = _QUOTED.findall(detail)
        if quoted:
            return {"symbol": "stamp", "text": quoted[0].upper()[:40]}
    if _NAMED_AFTER.search(text):
        names = re.findall(r"\b([A-Z][a-z]{3,})\b", text) or re.findall(r"\b([A-Z][a-z]{3,})\b", context)
        if names:
            return {"symbol": "plaque", "text": names[0].upper()}
    if _SIGNED.search(text):
        return {"symbol": "signature", "text": "Executive order"}
    return None


def deck_subjects(db: Session, project: VideoProject) -> list[Subject]:
    """Who and what this deck is about, in order.

    Three sources, deliberately unequal. The title says what the deck is *about*; the slide
    copy says what it *mentions*; the coverage only supplies depth. Treating them equally is
    how a deck titled "Trump's Focus" ends up led by Iran — one slide mentions the Iran war,
    and the news happens to hold eighteen Iran headlines.
    """
    item = project.content_item
    title_texts = [item.title or ""]
    deck_texts = [project.caption or ""] + [f"{s.get('on_screen_text', '')}. {s.get('subtext', '')}" for s in (project.scenes or [])]

    story = item.story if getattr(item, "story_id", None) else None
    if story is not None:
        coverage = [story.title or "", story.summary or "", story.why_it_matters or ""]
        coverage += [a.title or "" for a in getattr(story, "articles", [])[:20]]
    else:
        # No story attached — find the reporting by what the title names, not what a slide
        # happens to mention, or the search drifts to whatever is loudest in the news.
        coverage = _related_coverage(db, title_texts) or _related_coverage(db, title_texts + deck_texts)

    merged: dict[str, Subject] = {}
    for texts, weight, owned in ((title_texts, 12, True), (deck_texts, 3, True), (coverage, 1, False)):
        for subject in extract([x for x in texts if x], limit=12):
            key = subject.name.lower()
            existing = merged.get(key)
            if existing is None:
                subject.weight *= weight
                subject.from_deck = owned
                merged[key] = subject
            else:
                existing.weight += subject.weight * weight
                existing.from_deck = existing.from_deck or owned
    return sorted(merged.values(), key=lambda s: (-s.weight, -len(s.name)))[:8]


def _related_coverage(db: Session, texts: list[str], *, limit: int = 40) -> list[str]:
    """Headlines from the ingested news that name the same things these texts do."""
    seeds = {s.name for s in extract([x for x in texts if x], limit=3)}
    if not seeds:
        return []
    rows = db.execute(select(Article.title).order_by(Article.published_at.desc()).limit(600)).scalars().all()
    return [t for t in rows if t and any(seed.lower() in t.lower() for seed in seeds)][:limit]


def plan_scene_visual(scene: dict[str, Any], context: str = "", cast: list[Subject] | None = None) -> dict[str, Any]:
    """What this scene wants to show, before anything is fetched.

    Returns {"want": photo|symbol|illustration|none, "query": ..., "symbol": {...}, "mood": ...}
    """
    visual = scene.get("visual") or {}
    want = str(visual.get("want") or "").lower()
    if scene.get("visual_type") in ("chart", "comparison", "counter", "timeline", "list"):
        return {"want": "none"}  # it already has a visual that carries the point
    if visual.get("path"):
        return {"want": "none"}
    if want in ("photo", "symbol", "illustration", "none"):
        plan: dict[str, Any] = {"want": want, "mood": str(visual.get("mood") or "")}
        if want == "symbol":
            spec = {k: visual[k] for k in ("symbol", "old", "new", "text", "center", "left", "right") if k in visual}
            plan["symbol"] = spec if spec.get("symbol") in SYMBOLS else (infer_symbol(scene, context) or {})
        plan["query"] = str(visual.get("query") or "") or _subject_query(scene, cast)[0]
        plan["subject"], plan["thing"] = _subject_query(scene, cast)[1:]
        return plan
    symbol = infer_symbol(scene, context)
    if symbol:
        return {"want": "symbol", "symbol": symbol, "mood": ""}
    query, subject, thing = _subject_query(scene, cast)
    if visual.get("query"):
        query = str(visual["query"])
    return {"want": "photo" if query else "none", "query": query, "subject": subject, "thing": thing, "mood": ""}


# ---------------------------------------------------------------------------
# Applying it
# ---------------------------------------------------------------------------
def add_imagery(db: Session, project: VideoProject, *, allow_search: bool = True, allow_generate: bool = True, progress=None) -> VideoProject:
    """Give every scene that needs one a picture. Never overwrites a picture already chosen."""
    scenes = [dict(s) for s in (project.scenes or [])]
    if not scenes:
        return project
    context = f"{project.content_item.title} {project.caption or ''}"
    cast = deck_subjects(db, project)
    if cast:
        log.info("deck subjects: %s", ", ".join(f"{s.name}({s.weight})" for s in cast[:5]))
    policy = NetworkPolicy.load(db)
    can_search = allow_search and policy.allow_internet_research
    used: set[str] = set()
    used_symbols: set[str] = set()
    for i, scene in enumerate(scenes):
        if progress:
            progress(0.1 + 0.85 * i / len(scenes), f"Scene {i + 1}/{len(scenes)}")
        plan = plan_scene_visual(scene, context, cast)
        want = plan.get("want")
        visual = dict(scene.get("visual") or {})
        # Any picture the owner did not pin is provisional, and goes if it does not depict this
        # scene's subject. That is also how wrong pictures from an earlier, dumber version get
        # cleared: they carry no marker at all, because there was no marker to carry.
        # plan_scene_visual reports "none" for a scene that already has a picture, so the
        # subject is resolved directly here — judging that picture is the whole point.
        _, current_subject, current_thing = _subject_query(scene, cast)
        stale_picker = int(visual.get("picker") or 0) < PICKER_VERSION
        if visual.get("path") and not visual.get("pinned") and (stale_picker or not _still_depicts(db, visual, current_subject, current_thing)):
            log.info(
                "re-picking a picture (%s)",
                "chosen under older rules" if stale_picker else f"does not depict {getattr(current_subject, 'name', 'the subject')}",
            )
            for key in ("path", "image_id", "credit", "source_page", "generated", "auto", "query", "picker"):
                visual.pop(key, None)
            scene["visual"] = visual
            plan = plan_scene_visual(scene, context, cast)
            want = plan.get("want")
        if want == "none":
            continue

        symbol_spec = plan.get("symbol") or {}
        if want == "symbol" and symbol_spec:
            if symbol_spec.get("symbol") in used_symbols:
                plan = {**plan, "want": "photo", "query": plan.get("query") or _subject_query(scene, cast)[0]}
                want = plan["want"]
            else:
                used_symbols.add(str(symbol_spec.get("symbol")))
                scene["visual_type"] = "symbol"
                scene["role"] = "symbol"
                scene["visual"] = {**visual, **symbol_spec}
                continue

        row = None
        if want in ("photo", "illustration") and plan.get("query"):
            row = _from_library(db, plan["query"], exclude=used, subject=plan.get("subject"), thing=plan.get("thing", ""))
        if row is None and want == "photo" and can_search:
            try:
                for cand in search(db, plan["query"], limit=6, subject=plan.get("subject"), thing=plan.get("thing", "")):
                    if cand["url"] in used:
                        continue
                    try:
                        row = fetch(db, cand, content_item_id=project.content_item_id)
                        break
                    except (httpx.HTTPError, ValueError, OSError) as e:
                        log.info("skipping candidate %s: %s", cand.get("url"), e)
            except (ProviderError, PrivacyViolation) as e:
                log.warning("image search unavailable: %s", e)
        if row is None and want == "illustration" and allow_generate:
            row = generate_illustration(db, plan["query"], mood=plan.get("mood", ""), content_item_id=project.content_item_id)

        if row is not None:
            used.add(str((row.params or {}).get("url") or row.path))
            scene["visual_type"] = "image"
            scene["role"] = "image"
            scene["visual"] = {
                **visual,
                "path": row.path,
                "image_id": row.id,
                "credit": credit_line(row),
                "source_page": (row.params or {}).get("source_page", ""),
                "generated": bool(row.is_generated),
                "auto": True,
                "picker": PICKER_VERSION,
                "query": plan.get("query", ""),
                "treatment": visual.get("treatment") or ("full_bleed" if i == 0 else "band"),
            }
            continue

        # nothing available — fall back to a mark rather than leaving the slide bare
        symbol = plan.get("symbol") or infer_symbol(scene, context)
        if symbol and symbol.get("symbol") not in used_symbols:
            used_symbols.add(str(symbol.get("symbol")))
            scene["visual_type"] = "symbol"
            scene["role"] = "symbol"
            scene["visual"] = {**visual, **symbol}

    project.previous_scenes = project.scenes or []
    project.scenes = scenes
    project.render_status = "none"
    db.commit()
    return project


def _still_depicts(db: Session, visual: dict[str, Any], subject: Subject | None, thing: str) -> bool:
    """Does the picture on this scene actually show the scene's subject?

    Scored against the stored title where we have one, and the filename otherwise — pictures
    attached before subjects existed carry no metadata, and those are exactly the ones most
    likely to be wrong.
    """
    if subject is None:
        return True
    if visual.get("generated"):
        return True  # drawn to order for this scene
    path = str(visual.get("path") or "")
    row = db.execute(select(Image).where(Image.path == path)).scalar_one_or_none() if path else None
    described = f"{row.title} {row.prompt}" if row is not None else re.sub(r"[-_]+", " ", Path(path).stem)
    return score_candidate(described, subject, thing=thing) > 0


def _from_library(db: Session, query: str, *, exclude: set[str], subject: Subject | None = None, thing: str = "") -> Image | None:
    """Reuse a picture already downloaded — but only one that clears the same relevance bar
    as a fresh search, or the library becomes a cache of yesterday's wrong guesses."""
    rows = db.execute(select(Image).where(Image.label.in_(("photo", "illustration"))).order_by(Image.created_at.desc()).limit(200)).scalars().all()
    best: tuple[int, Image] | None = None
    for row in rows:
        if row.path in exclude or not row.path:
            continue
        hay = f"{row.title} {row.prompt}"
        if subject is not None:
            score = score_candidate(hay, subject, thing=thing)
            if score > 0 and (best is None or score > best[0]):
                best = (score, row)
            continue
        terms = [t for t in query.lower().split() if len(t) > 3][:3]
        if terms and sum(t in hay.lower() for t in terms) >= max(1, len(terms) - 1):
            return row
    return best[1] if best else None
