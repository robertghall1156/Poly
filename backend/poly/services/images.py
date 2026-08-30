"""Deterministic image rendering (memes, quote cards, charts, simple infographics) with Pillow,
plus the optional local generative provider. No cloud calls."""
from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Image
from ..providers.base import ProviderError
from ..providers.image.local_generative import LocalGenerativeImageProvider

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _hex(c: str, default=(18, 72, 126)) -> tuple[int, int, int]:
    c = (c or "").lstrip("#")
    if len(c) != 6:
        return default
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines = []
    for para in text.split("\n"):
        words = para.split()
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textlength(test, font=font) <= max_width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _fit_font(draw, text, max_width, max_height, start=72, minimum=24):
    size = start
    while size >= minimum:
        font = _font(size)
        lines = _wrap(draw, text, font, max_width)
        h = len(lines) * size * 1.25
        if h <= max_height and all(draw.textlength(l, font=font) <= max_width for l in lines):
            return font, lines
        size -= 4
    font = _font(minimum)
    return font, _wrap(draw, text, font, max_width)


def _out(kind: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    return get_settings().images_path / f"{kind}-{stamp}.png"


def render_text_meme(top: str, bottom: str = "", *, base_image: str | None = None, width: int = 1080, height: int = 1080, bg: str = "#12487E") -> Path:
    if base_image and Path(base_image).exists():
        img = PILImage.open(base_image).convert("RGB")
        img = img.resize((width, int(width * img.height / img.width)))
        height = img.height
    else:
        img = PILImage.new("RGB", (width, height), _hex(bg))
    draw = ImageDraw.Draw(img)
    for text, anchor in ((top.upper(), "top"), (bottom.upper(), "bottom")):
        if not text:
            continue
        font, lines = _fit_font(draw, text, int(width * 0.9), int(height * 0.3), start=88)
        line_h = int(font.size * 1.2)
        total_h = line_h * len(lines)
        y = int(height * 0.04) if anchor == "top" else height - total_h - int(height * 0.04)
        for line in lines:
            w = draw.textlength(line, font=font)
            x = (width - w) / 2
            draw.text((x, y), line, font=font, fill="white", stroke_width=max(2, font.size // 14), stroke_fill="black")
            y += line_h
    path = _out("meme")
    img.save(path)
    return path


def render_quote_card(quote: str, attribution: str = "", *, width: int = 1080, height: int = 1080, bg: str = "#12487E", accent: str = "#F46543", brand: str = "") -> Path:
    img = PILImage.new("RGB", (width, height), _hex(bg))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (int(width * 0.02), height)], fill=_hex(accent, (244, 101, 67)))
    font, lines = _fit_font(draw, f"“{quote}”", int(width * 0.8), int(height * 0.6), start=72, minimum=30)
    line_h = int(font.size * 1.3)
    y = (height - line_h * len(lines)) / 2 - height * 0.05
    for line in lines:
        draw.text((width * 0.1, y), line, font=font, fill="white")
        y += line_h
    if attribution:
        f2 = _font(38)
        draw.text((width * 0.1, y + 30), f"— {attribution}", font=f2, fill=_hex(accent, (244, 101, 67)))
    if brand:
        f3 = _font(30)
        draw.text((width * 0.1, height - 80), brand, font=f3, fill=(200, 210, 220))
    path = _out("quote")
    img.save(path)
    return path


def render_bar_chart(title: str, labels: list[str], values: list[float], *, source: str = "", width: int = 1600, height: int = 1000, bg: str = "#FFFFFF", bar: str = "#12487E", accent: str = "#F46543", unit: str = "") -> Path:
    img = PILImage.new("RGB", (width, height), _hex(bg, (255, 255, 255)))
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), title, font=_font(52), fill=(20, 20, 20))
    n = max(1, len(values))
    vmax = max([abs(v) for v in values] + [1e-9])
    left, right, top, bottom = 80, width - 60, 160, height - 160
    gap = (right - left) / n
    bw = gap * 0.6
    for i, (lab, val) in enumerate(zip(labels, values)):
        h = (bottom - top) * (abs(val) / vmax)
        x0 = left + i * gap + (gap - bw) / 2
        color = _hex(accent) if i == max(range(n), key=lambda k: values[k]) else _hex(bar)
        draw.rectangle([(x0, bottom - h), (x0 + bw, bottom)], fill=color)
        vt = f"{val:,.0f}{unit}" if abs(val) >= 10 else f"{val:,.1f}{unit}"
        f = _font(30)
        draw.text((x0 + bw / 2 - draw.textlength(vt, font=f) / 2, bottom - h - 40), vt, font=f, fill=(30, 30, 30))
        f2 = _font(28)
        for k, line in enumerate(textwrap.wrap(str(lab), 14)[:2]):
            draw.text((x0 + bw / 2 - draw.textlength(line, font=f2) / 2, bottom + 12 + k * 32), line, font=f2, fill=(60, 60, 60))
    draw.line([(left, bottom), (right, bottom)], fill=(120, 120, 120), width=2)
    if source:
        draw.text((60, height - 60), f"Source: {source}", font=_font(26), fill=(110, 110, 110))
    path = _out("chart")
    img.save(path)
    return path


def render_infographic(title: str, points: list[str], *, width: int = 1080, height: int = 1350, bg: str = "#12487E", accent: str = "#F46543", source: str = "") -> Path:
    img = PILImage.new("RGB", (width, height), _hex(bg))
    draw = ImageDraw.Draw(img)
    font, lines = _fit_font(draw, title, int(width * 0.86), int(height * 0.18), start=72, minimum=36)
    y = 70
    for line in lines:
        draw.text((width * 0.07, y), line, font=font, fill="white")
        y += int(font.size * 1.25)
    y += 30
    draw.line([(width * 0.07, y), (width * 0.93, y)], fill=_hex(accent), width=6)
    y += 40
    body = _font(38)
    for i, p in enumerate(points[:7], 1):
        draw.ellipse([(width * 0.07, y + 8), (width * 0.07 + 44, y + 52)], fill=_hex(accent))
        num = _font(30)
        draw.text((width * 0.07 + 22 - draw.textlength(str(i), font=num) / 2, y + 12), str(i), font=num, fill="white")
        for line in _wrap(draw, p, body, int(width * 0.78)):
            draw.text((width * 0.07 + 70, y), line, font=body, fill="white")
            y += 48
        y += 26
        if y > height - 120:
            break
    if source:
        draw.text((width * 0.07, height - 70), f"Source: {source}", font=_font(26), fill=(200, 210, 220))
    path = _out("infographic")
    img.save(path)
    return path


def create_image(db: Session, *, kind: str, params: dict[str, Any], content_item_id: str | None = None, title: str = "") -> Image:
    """Dispatch to a renderer and record the Image row (with prompt/params metadata)."""
    is_generated = False
    provider = "deterministic"
    label = "chart"
    if kind == "text_meme":
        path = render_text_meme(params.get("top", ""), params.get("bottom", ""), base_image=params.get("base_image"), bg=params.get("bg", "#12487E"))
        label = "satire" if params.get("satire", True) else "chart"
    elif kind == "quote_card":
        path = render_quote_card(params.get("quote", ""), params.get("attribution", ""), bg=params.get("bg", "#12487E"), accent=params.get("accent", "#F46543"), brand=params.get("brand", ""))
        label = "chart"
    elif kind == "chart":
        path = render_bar_chart(params.get("title", ""), list(params.get("labels", [])), [float(v) for v in params.get("values", [])], source=params.get("source", ""), unit=params.get("unit", ""))
    elif kind == "infographic":
        path = render_infographic(params.get("title", ""), list(params.get("points", [])), source=params.get("source", ""))
    elif kind == "generated":
        prov = LocalGenerativeImageProvider()
        if not prov.available():
            raise ProviderError("No local image-generation model is configured. Set POLY_LOCAL_IMAGE_URL (see README → Local image generation).", provider="image", retryable=False)
        out = _out("generated")
        res = prov.generate(params.get("prompt", ""), out_path=str(out), width=int(params.get("width", 1024)), height=int(params.get("height", 1024)))
        path = Path(res.path)
        is_generated, provider, label = True, prov.name, "generated"
    else:
        raise ValueError(f"unknown image kind {kind}")
    with PILImage.open(path) as im:
        w, h = im.size
    row = Image(kind=kind, title=title or params.get("title") or params.get("top") or params.get("quote", "")[:100], prompt=params.get("prompt", ""), provider=provider, params=params, path=str(path), width=w, height=h, is_generated=is_generated, label=label, content_item_id=content_item_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def image_provider_status() -> dict[str, Any]:
    prov = LocalGenerativeImageProvider()
    return {"configured": bool(prov.base_url), "kind": prov.kind if prov.base_url else "", "endpoint": prov.base_url, "available": prov.available() if prov.base_url else False, "deterministic": True}
