"""Meme Studio: concept generation + deterministic template rendering (Pillow, brand tokens).

Templates: two_buttons, expectation_reality, how_started_going, system_says, politicians_people,
before_after, think_vs_happens, classic, custom (classic layout over an uploaded/generated image).
Humor guidance favors observational / irony / system-absurdity / bureaucracy / economic / AI humor
over partisan rage bait.
"""
from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Image
from ..providers.registry import Router
from .faceless import resolve_source
from .images import _fit_font, _font, _hex
from .llm_utils import as_list, as_str, chat_json
from .render_video import _darken, _vertical_gradient, load_brand
from .voice import INTEGRITY, VOICE

MEME_TEMPLATES = [
    "two_buttons", "expectation_reality", "how_started_going", "system_says", "politicians_people",
    "before_after", "think_vs_happens", "classic", "custom",
]

SYSTEM_MEMES = f"""{VOICE}
{INTEGRITY}
You write meme concepts. Humor styles allowed: observational, irony, system absurdity, historical
comparison, bureaucracy humor, economic humor, AI humor. NOT allowed: rage bait, cheap insults,
fabricated quotes, partisan dunking for its own sake, or anything targeting private individuals.
Return JSON: {{"concepts": [3 items, each {{
  "template": one of {MEME_TEMPLATES[:-1]},
  "concept": "one line describing the joke",
  "visual": "what the image shows (for classic: the background idea)",
  "top_text": "≤10 words",
  "bottom_text": "≤10 words",
  "caption": "post caption ≤150 chars, may invite discussion",
  "why_it_works": "one sentence",
  "humor_type": "which allowed style this is"}}]}}
Make the three concepts use different templates and different humor styles."""

_TEMPLATE_LABELS = {
    "two_buttons": ("Button 1", "Button 2"),
    "expectation_reality": ("EXPECTATION", "REALITY"),
    "how_started_going": ("HOW IT STARTED", "HOW IT'S GOING"),
    "system_says": ("THE SYSTEM SAYS", "REALITY"),
    "politicians_people": ("POLITICIANS", "PEOPLE"),
    "before_after": ("BEFORE", "AFTER"),
    "think_vs_happens": ("WHAT PEOPLE THINK", "WHAT ACTUALLY HAPPENS"),
}


def generate_concepts(db: Session, *, source: dict[str, Any] | None = None, idea: str = "", humor: str = "", router: Router | None = None) -> list[dict[str, Any]]:
    router = router or Router(db)
    material = ""
    if source and any(source.values()):
        _, material, _ = resolve_source(db, source)
    if idea:
        material += f"\nIDEA: {idea}"
    if humor:
        material += f"\nPREFERRED HUMOR STYLE: {humor}"
    if not material.strip():
        raise ValueError("provide a source or an idea")
    data, res = chat_json(router, "FAST", "meme_concepts", SYSTEM_MEMES, material, temperature=0.85, max_tokens=1200)
    out = []
    for c in as_list(data.get("concepts"))[:5]:
        if not isinstance(c, dict):
            continue
        tpl = as_str(c.get("template"))
        out.append(
            {
                "template": tpl if tpl in MEME_TEMPLATES else "classic",
                "concept": as_str(c.get("concept"))[:200],
                "visual": as_str(c.get("visual"))[:300],
                "top_text": as_str(c.get("top_text"))[:120],
                "bottom_text": as_str(c.get("bottom_text"))[:120],
                "caption": as_str(c.get("caption"))[:300],
                "why_it_works": as_str(c.get("why_it_works"))[:300],
                "humor_type": as_str(c.get("humor_type"))[:60],
                "model": res.model,
            }
        )
    if not out:
        raise ValueError("no meme concepts generated — try again or add an idea")
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
SIZE = 1080


def _canvas(brand: dict, dark: bool = True) -> PILImage.Image:
    base = _hex(brand.get("primary", "#102A43")) if dark else _hex(brand.get("background", "#F8F9FA"))
    return _vertical_gradient(base, _darken(base, 0.86 if dark else 0.97), SIZE, SIZE)


def _outlined(draw, xy, text, font, fill, anchor_center_x=None):
    x, y = xy
    if anchor_center_x is not None:
        x = anchor_center_x - draw.textlength(text, font=font) / 2
    draw.text((x, y), text, font=font, fill=fill, stroke_width=max(2, font.size // 16), stroke_fill="black")


def _split_panels(img, draw, brand, label_a, label_b, text_a, text_b, *, horizontal=False):
    fg = _hex(brand.get("text_on_dark", "#F8F9FA"))
    accent = _hex(brand.get("accent", "#0F766E"))
    gold = _hex(brand.get("highlight", "#C89B3C"))
    pad = 50
    boxes = ([(pad, 150, SIZE / 2 - 20, SIZE - pad), (SIZE / 2 + 20, 150, SIZE - pad, SIZE - pad)] if not horizontal
             else [(pad, 150, SIZE - pad, SIZE / 2 + 30), (pad, SIZE / 2 + 90, SIZE - pad, SIZE - pad)])
    for (box, label, text, color) in zip(boxes, (label_a, label_b), (text_a, text_b), (accent, gold)):
        # avoid double labels when the text already starts with the panel label
        low = text.lower().lstrip()
        for prefix in (label.lower() + ":", label.lower()):
            if low.startswith(prefix):
                text = text.lstrip()[len(prefix):].lstrip(" :.-") or text
                break
        draw.rounded_rectangle(box, radius=26, fill=_darken(color, 0.22), outline=color, width=5)
        lf = _font(40)
        draw.text(((box[0] + box[2]) / 2 - draw.textlength(label, font=lf) / 2, box[1] + 26), label, font=lf, fill=color)
        f, lines = _fit_font(draw, text, int(box[2] - box[0] - 60), int(box[3] - box[1] - 140), start=54, minimum=28)
        y = (box[1] + box[3]) / 2 - len(lines) * f.size * 0.62
        for line in lines:
            draw.text(((box[0] + box[2]) / 2 - draw.textlength(line, font=f) / 2, y), line, font=f, fill=fg)
            y += f.size * 1.22


def render_meme(db: Session, *, template: str, top_text: str = "", bottom_text: str = "", title: str = "", base_image: str | None = None, content_item_id: str | None = None, params: dict[str, Any] | None = None) -> Image:
    brand = load_brand(db)
    params = dict(params or {})
    fg = _hex(brand.get("text_on_dark", "#F8F9FA"))
    gold = _hex(brand.get("highlight", "#C89B3C"))
    is_generated = False
    label = "satire"

    if template in _TEMPLATE_LABELS:
        img = _canvas(brand)
        draw = ImageDraw.Draw(img)
        la, lb = _TEMPLATE_LABELS[template]
        if title:
            tf = _font(44)
            _outlined(draw, (0, 60), title, tf, fg, anchor_center_x=SIZE / 2)
        if template == "two_buttons":
            # two big buttons + a sweating chooser bar at the bottom
            _split_panels(img, draw, brand, "OPTION A", "OPTION B", top_text, bottom_text)
            draw.rounded_rectangle([(SIZE * 0.2, SIZE - 130), (SIZE * 0.8, SIZE - 60)], radius=20, fill=_hex(brand.get("secondary", "#52667A")))
            cf = _font(34)
            choose = params.get("chooser_text", "…every Congress, every year")
            draw.text((SIZE / 2 - draw.textlength(choose, font=cf) / 2, SIZE - 118), choose, font=cf, fill=fg)
        else:
            horizontal = template in ("expectation_reality", "how_started_going", "before_after", "think_vs_happens", "system_says")
            _split_panels(img, draw, brand, la, lb, top_text, bottom_text, horizontal=horizontal)
    else:  # classic / custom: big top & bottom text over background or image
        if base_image and Path(base_image).exists():
            with PILImage.open(base_image) as src:
                img = src.convert("RGB").resize((SIZE, int(SIZE * src.height / src.width)))
            if params.get("generated"):
                is_generated = True
        else:
            img = _canvas(brand)
        draw = ImageDraw.Draw(img)
        wpx = int(img.width * 0.92)
        for text, at_top in ((top_text, True), (bottom_text, False)):
            if not text:
                continue
            f, lines = _fit_font(draw, text.upper(), wpx, int(img.height * 0.28), start=92, minimum=36)
            y = int(img.height * 0.04) if at_top else img.height - int(len(lines) * f.size * 1.22) - int(img.height * 0.05)
            for line in lines:
                _outlined(draw, (0, y), line, f, "white", anchor_center_x=img.width / 2)
                y += f.size * 1.2
        draw = ImageDraw.Draw(img)
    if is_generated:
        gf = _font(26)
        draw.text((20, img.height - 40), "AI-generated image", font=gf, fill=gold)

    from datetime import datetime

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    path = get_settings().images_path / f"meme-{template}-{stamp}.png"
    img.save(path)
    row = Image(
        kind="text_meme", title=(title or top_text or template)[:300], prompt=params.get("prompt", ""),
        provider="deterministic", params={"template": template, "top_text": top_text, "bottom_text": bottom_text, **params},
        path=str(path), width=img.width, height=img.height, is_generated=is_generated, label=label,
        content_item_id=content_item_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
