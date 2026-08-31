"""Scene composition: a VideoScene dict → designed frames.

Two layers, so the video and the still preview share one design:

    compose_base(scene, …)  → RGB   surface, furniture, data visual
    compose_text(scene, …)  → RGBA  headline + body only (the part that animates)
    compose(scene, …)       → RGB   both, flattened (editor preview, carousel slides)

Layout is role-driven — cover, point, stat, chart, contrast, quote, list, timeline,
image, question, closer — so a six-slide deck reads as a designed sequence instead of
six identical text cards.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw, ImageOps

from .design import (
    Ink,
    Line,
    Palette,
    clean_headline,
    corner_ticks,
    draw_lines,
    fit,
    font,
    hairline_grid,
    ink_for,
    mix,
    role_for,
    sanitize,
    sentence,
    shade,
    small_caps,
    surface,
    surface_for,
    wrap,
)
from .symbols import draw_symbol

SCRATCH = ImageDraw.Draw(PILImage.new("RGB", (8, 8)))


def is_full_bleed(scene: dict[str, Any]) -> bool:
    """A picture used as the whole frame rather than an element inside it."""
    v = scene.get("visual") or {}
    return bool(str(v.get("treatment") or "") == "full_bleed" and v.get("path") and Path(str(v["path"])).exists())


def _cover_crop(path: str, w: int, h: int) -> PILImage.Image:
    with PILImage.open(path) as src:
        src = src.convert("RGB")
        scale = max(w / src.width, h / src.height)
        resized = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), PILImage.LANCZOS)
    left = (resized.width - w) // 2
    top = int((resized.height - h) * 0.35)  # faces sit above centre
    return resized.crop((left, top, left + w, top + h))


def _duotone(im: PILImage.Image, pal: Palette, *, strength: float = 1.0) -> PILImage.Image:
    """Push a photograph into the brand's two-colour range so it can't fight the palette."""
    toned = ImageOps.colorize(ImageOps.autocontrast(im.convert("L"), cutoff=1), black=shade(pal.ink, 0.55), white=shade(pal.paper, 1.0), mid=mix(pal.accent, pal.ink, 0.35))
    return PILImage.blend(im, toned, max(0.0, min(1.0, strength)))


def _full_bleed_surface(scene: dict[str, Any], pal: Palette, width: int, height: int) -> PILImage.Image:
    """The picture as the frame, with a scrim heavy enough that type stays readable over it."""
    v = scene.get("visual") or {}
    img = _duotone(_cover_crop(str(v["path"]), width, height), pal, strength=float(v.get("duotone", 0.72)))
    scrim = PILImage.new("RGBA", (1, height), (0, 0, 0, 0))
    px = scrim.load()
    ink = shade(pal.ink, 0.55)
    for y in range(height):
        t = y / max(1, height - 1)
        # light veil throughout for the rails, deepening into the lower third for the headline
        a = 0.22 + 0.68 * max(0.0, (t - 0.34) / 0.66) ** 1.5
        px[0, y] = (*ink, int(255 * min(0.94, a)))
    img.paste(scrim.resize((width, height)), (0, 0), scrim.resize((width, height)))
    return img


@dataclass
class Frame:
    w: int
    h: int

    @property
    def margin(self) -> int:
        return int(self.w * 0.089)

    @property
    def column(self) -> int:
        return self.w - 2 * self.margin

    @property
    def rail_y(self) -> int:
        return int(self.h * 0.055)

    @property
    def top(self) -> int:
        return int(self.h * 0.135)

    @property
    def bottom(self) -> int:
        return self.h - int(self.h * 0.115)

    @property
    def unit(self) -> float:
        """Type scale reference — a short (1920 tall) carries larger type than a 1350 slide."""
        return self.w / 1080


@dataclass
class Plan:
    scene: dict[str, Any]
    role: str
    headline: str
    body: str
    head_font: Any
    head_lines: list[Line]
    head_xy: tuple[float, float]
    head_align: str
    body_font: Any
    body_lines: list[Line]
    body_xy: tuple[float, float]
    body_align: str
    visual_box: tuple[int, int, int, int] | None
    leading: float


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def _plan(scene: dict[str, Any], fr: Frame, role: str, index: int, total: int) -> Plan:
    d = SCRATCH
    u = fr.unit
    col = fr.column
    headline = clean_headline(sanitize(str(scene.get("on_screen_text") or ""))[0])
    body = sentence(sanitize(str(scene.get("subtext") or ""))[0])
    vt = str(scene.get("visual_type") or "text").lower()
    full_bleed = is_full_bleed(scene)
    has_visual = (not full_bleed) and role in ("chart", "contrast", "timeline", "list", "image", "symbol")

    # --- headline sizing per role ---------------------------------------------
    if role == "cover" or full_bleed:
        head_size, weight, leading, align, max_lines = int(122 * u), 800, 0.98, "left", 5
    elif role == "question":
        head_size, weight, leading, align, max_lines = int(96 * u), 800, 1.04, "center", 5
    elif role == "quote":
        head_size, weight, leading, align, max_lines = int(84 * u), 700, 1.12, "left", 7
    elif role == "stat":
        head_size, weight, leading, align, max_lines = int(64 * u), 800, 1.04, "center", 3
    elif role == "closer":
        head_size, weight, leading, align, max_lines = int(116 * u), 800, 1.0, "left", 4
    elif has_visual:
        head_size, weight, leading, align, max_lines = int(72 * u), 800, 1.02, "left", 3
    else:
        head_size, weight, leading, align, max_lines = int(120 * u), 800, 1.0, "left", 5

    head_budget = fr.h * (0.30 if not has_visual else 0.18)
    head_font, head_lines = fit(d, headline, col, head_budget, weight=weight, start=head_size, minimum=int(34 * u), leading=leading, max_lines=max_lines)
    head_h = len(head_lines) * head_font.size * leading if headline else 0

    body_size = int((52 if not has_visual else 38) * u)
    body_font = font(body_size, 400)
    body_col = col if align != "center" else col * 0.92
    body_lines = wrap(d, body, body_font, body_col)[:6] if body else []
    body_lead = 1.34
    body_h = len(body_lines) * body_size * body_lead if body_lines else 0
    gap = head_font.size * 0.52 if headline and body_lines else 0

    x = fr.margin
    visual_box: tuple[int, int, int, int] | None = None

    if role == "cover" or full_bleed:
        total_h = head_h + gap + body_h
        y = fr.bottom - total_h - int(fr.h * 0.045)
        head_xy, body_xy = (x, y), (x, y + head_h + gap)
    elif role == "question":
        total_h = head_h + gap + body_h
        y = (fr.top + fr.bottom) / 2 - total_h / 2
        head_xy, body_xy = (x, y), (x + (col - body_col) / 2, y + head_h + gap)
    elif role == "quote":
        total_h = head_h + gap + body_h
        y = (fr.top + fr.bottom) / 2 - total_h / 2
        head_xy, body_xy = (x + int(48 * u), y), (x + int(48 * u), y + head_h + gap)
    elif role == "stat":
        head_xy = (x, fr.top + int(24 * u))
        body_xy = (x, fr.bottom - body_h)
        visual_box = (x, int(fr.top + head_h + fr.h * 0.10), fr.w - fr.margin, int(fr.bottom - body_h - fr.h * 0.05))
    elif role == "closer":
        total_h = head_h + gap + body_h
        y = (fr.top + fr.bottom) / 2 - total_h / 2
        head_xy, body_xy = (x, y), (x, y + head_h + gap)
    elif has_visual:
        y = fr.top + int(20 * u)
        head_xy = (x, y)
        body_top = fr.bottom - body_h
        body_xy = (x, body_top)
        vy0 = int(y + head_h + fr.h * 0.045)
        vy1 = int((body_top - fr.h * 0.045) if body_lines else fr.bottom)
        visual_box = (x, vy0, fr.w - fr.margin, max(vy0 + int(120 * u), vy1))
    else:  # point — set in the upper third, so the space below reads as margin, not a gap
        total_h = head_h + gap + body_h
        y = fr.top + max(int(fr.h * 0.045), (fr.bottom - fr.top - total_h) * 0.30)
        head_xy, body_xy = (x, y), (x, y + head_h + gap)

    if vt == "counter" and role != "stat" and visual_box is None:
        visual_box = (x, int(fr.h * 0.45), fr.w - fr.margin, int(fr.h * 0.66))

    return Plan(
        scene=scene,
        role=role,
        headline=headline,
        body=body,
        head_font=head_font,
        head_lines=head_lines if headline else [],
        head_xy=head_xy,
        head_align=align,
        body_font=body_font,
        body_lines=body_lines,
        body_xy=body_xy,
        body_align="center" if align == "center" else "left",
        visual_box=visual_box,
        leading=leading,
    )


# ---------------------------------------------------------------------------
# Base layer: surface, furniture, data visual
# ---------------------------------------------------------------------------
def compose_base(scene: dict[str, Any], brand: dict[str, Any], *, width: int, height: int, index: int = 0, total: int = 1, animate_counter: bool = False) -> PILImage.Image:
    pal = Palette.from_brand(brand)
    fr = Frame(width, height)
    role = role_for(scene, index, total)
    if is_full_bleed(scene):
        img = _full_bleed_surface(scene, pal, width, height)
        base, dark = shade(pal.ink, 0.55), True
    else:
        img, base, dark = surface(pal, surface_for(scene, index, total, role), width, height)
    ink = ink_for(pal, base, dark)
    draw = ImageDraw.Draw(img)
    u = fr.unit
    plan = _plan(scene, fr, role, index, total)

    _decorate(draw, img, fr, plan, ink, pal, base, dark, index, total)
    hairline_grid(draw, width, height, fr.margin - int(20 * u), ink)
    _rail(draw, fr, ink, pal, index, total, scene, role)

    if plan.visual_box:
        _visual(draw, img, plan.visual_box, scene, ink, pal, u, role, dark, animate_counter=animate_counter)

    _footer(draw, fr, ink, scene, index, total, role, u)
    return img


def _decorate(draw, img, fr: Frame, plan: Plan, ink: Ink, pal: Palette, base, dark: bool, index: int, total: int) -> None:
    u = fr.unit
    role = plan.role
    x, y = plan.head_xy

    if is_full_bleed(plan.scene):
        draw.rectangle([(x, y - int(46 * u)), (x + int(150 * u), y - int(46 * u) + int(9 * u))], fill=ink.highlight)
        draw.rectangle([(0, fr.h - int(14 * u)), (fr.w, fr.h)], fill=pal.highlight)
    elif role == "cover":
        # oversized index mark bleeding off the right edge — the magazine-cover move
        mark = font(int(760 * u), 800)
        label = f"{index + 1:02d}"
        draw.text((fr.w - int(60 * u) - draw.textlength(label, font=mark), -int(120 * u)), label, font=mark, fill=mix(base, ink.strong, 0.07))
        draw.rectangle([(x, y - int(46 * u)), (x + int(150 * u), y - int(46 * u) + int(9 * u))], fill=ink.highlight)
        draw.rectangle([(0, fr.h - int(14 * u)), (fr.w, fr.h)], fill=pal.highlight)
    elif role == "point":
        n = font(int(150 * u), 800)
        label = f"{index + 1:02d}"
        draw.text((x, plan.head_xy[1] - int(190 * u)), label, font=n, fill=mix(base, ink.highlight, 0.55))
        draw.rectangle([(x, plan.head_xy[1] - int(34 * u)), (x + int(110 * u), plan.head_xy[1] - int(34 * u) + int(7 * u))], fill=ink.accent)
    elif role == "question":
        pad = int(56 * u)
        box = (fr.margin - pad // 2, plan.head_xy[1] - pad, fr.w - fr.margin + pad // 2, plan.body_xy[1] + len(plan.body_lines) * plan.body_font.size * 1.34 + pad * 0.4)
        corner_ticks(draw, box, ink.highlight, size=int(46 * u), width=int(5 * u))
    elif role == "quote":
        q = font(int(280 * u), 800)
        draw.text((fr.margin - int(14 * u), plan.head_xy[1] - int(150 * u)), "“", font=q, fill=mix(base, ink.highlight, 0.45))
        draw.rectangle([(fr.margin, plan.head_xy[1]), (fr.margin + int(8 * u), plan.head_xy[1] + len(plan.head_lines) * plan.head_font.size * plan.leading)], fill=ink.highlight)
    elif role == "closer":
        draw.rectangle([(x, y - int(42 * u)), (x + int(150 * u), y - int(42 * u) + int(9 * u))], fill=ink.highlight)
        draw.rectangle([(0, fr.h - int(16 * u)), (fr.w, fr.h)], fill=shade(base, 0.7 if dark else 1.0))
    elif role == "stat":
        pass
    else:
        draw.rectangle([(x, y - int(34 * u)), (x + int(110 * u), y - int(34 * u) + int(7 * u))], fill=ink.accent)


def _rail(draw, fr: Frame, ink: Ink, pal: Palette, index: int, total: int, scene: dict, role: str) -> None:
    u = fr.unit
    y = fr.rail_y
    logo = pal.logo or ""
    if logo:
        small_caps(draw, (fr.margin, y), logo, int(26 * u), ink.faint)
    kicker = str(scene.get("kicker") or "").strip()
    if not kicker and role == "cover":
        kicker = str(scene.get("source") or "")
    if kicker:
        f = font(int(26 * u), 700)
        w = draw.textlength(kicker.upper(), font=f) + int(26 * u) * 0.14 * max(0, len(kicker) - 1)
        small_caps(draw, (fr.w - fr.margin - w, y), kicker, int(26 * u), ink.highlight)
    draw.line([(fr.margin, y + int(46 * u)), (fr.w - fr.margin, y + int(46 * u))], fill=ink.rule, width=max(1, int(2 * u)))


def _footer(draw, fr: Frame, ink: Ink, scene: dict, index: int, total: int, role: str, u: float) -> None:
    y = fr.h - int(fr.h * 0.052)
    if role != "cover":
        draw.line([(fr.margin, y - int(30 * u)), (fr.w - fr.margin, y - int(30 * u))], fill=ink.rule, width=max(1, int(2 * u)))
    visual = scene.get("visual") or {}
    bits = []
    if visual.get("generated"):
        bits.append("AI-generated illustration")   # never optional: it is not a photograph
    elif visual.get("credit"):
        bits.append(f"Photo: {visual['credit']}")
    src = str(scene.get("source") or visual.get("source") or "")
    if src and role != "cover":
        bits.append(f"Source: {src}")
    if bits:
        rail_w = ((30 + 9) * u * total + 40 * u) if total > 1 else 0
        avail = fr.w - 2 * fr.margin - rail_w
        size = int(21 * u)
        f = font(size, 700)

        def too_wide(s: str) -> bool:
            return draw.textlength(s.upper(), font=f) + size * 0.14 * max(0, len(s) - 1) > avail

        # drop whole items before cutting words — "Photo: … · S…" helps nobody
        while len(bits) > 1 and too_wide(" · ".join(bits)):
            bits.pop()
        text = " · ".join(bits)
        while text and too_wide(text):
            text = text[:-2].rstrip(" ·")
        small_caps(draw, (fr.margin, y), text, size, ink.faint)
    footer, arrow = sanitize(str((scene.get("visual") or {}).get("footer") or ""))
    if footer:
        fw = small_caps(draw, (fr.margin, y - int(34 * u)), footer[:40], int(24 * u), ink.highlight)
        if arrow:  # the font has no arrow glyph, so draw one
            ax = fr.margin + fw + int(16 * u)
            ay = y - int(34 * u) + int(12 * u)
            s = int(11 * u)
            draw.polygon([(ax, ay - s), (ax + s * 1.5, ay), (ax, ay + s)], fill=ink.highlight)
    if total > 1:
        # progress rail rather than "3/6" — reads instantly, looks intentional
        seg_w = int(30 * u)
        gap = int(9 * u)
        x1 = fr.w - fr.margin
        x0 = x1 - (seg_w + gap) * total + gap
        for i in range(total):
            sx = x0 + i * (seg_w + gap)
            draw.rectangle([(sx, y + int(8 * u)), (sx + seg_w, y + int(13 * u))], fill=ink.highlight if i == index else ink.rule)


# ---------------------------------------------------------------------------
# Data visuals
# ---------------------------------------------------------------------------
def _visual(draw, img, box, scene: dict, ink: Ink, pal: Palette, u: float, role: str, dark: bool, *, animate_counter: bool = False) -> None:
    visual = scene.get("visual") or {}
    vt = str(scene.get("visual_type") or "").lower()
    if role == "stat" or vt == "counter":
        _stat(draw, box, visual, ink, u, number=not animate_counter)
    elif role == "chart" and visual.get("values"):
        _bars(draw, box, visual, ink, u)
    elif role == "contrast" and visual.get("left"):
        _contrast(draw, box, visual, ink, u)
    elif role == "timeline" and visual.get("points"):
        _timeline(draw, box, visual, ink, u)
    elif role == "list" and visual.get("items"):
        _list(draw, box, visual, ink, u)
    elif role == "image" and visual.get("path") and Path(str(visual["path"])).exists():
        _image(img, draw, box, visual, ink, pal, u, dark)
    elif role == "symbol":
        draw_symbol(img, box, visual, ink, pal, u)


def _pack(box, n: int, max_row: float) -> tuple[float, float]:
    """Rows sized to the content, then centred in the band — stretching n rows across a
    tall box is what makes a visual look like scattered text."""
    x0, y0, x1, y1 = box
    row = min((y1 - y0) / max(1, n), max_row)
    return row, y0 + ((y1 - y0) - row * n) / 2


def _abbrev(v: float) -> str:
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.1f}B".replace(".0B", "B")
    if a >= 1e6:
        return f"{v / 1e6:.1f}M".replace(".0M", "M")
    if a >= 1e4:
        return f"{v / 1e3:.0f}K"
    return f"{v:,.0f}" if abs(v) >= 10 else f"{v:,.1f}"


def _stat(draw, box, visual, ink: Ink, u: float, *, number: bool = True) -> None:
    x0, y0, x1, y1 = box
    try:
        value = float(visual.get("to", visual.get("value", 0)) or 0)
    except (TypeError, ValueError):
        value = 0.0
    text = f"{visual.get('prefix', '')}{_abbrev(value)}{visual.get('suffix', '')}"
    f, lines = fit(SCRATCH, text, x1 - x0, (y1 - y0) * 0.72, weight=800, start=int(300 * u), minimum=int(90 * u), leading=0.98, max_lines=1)
    ln = lines[0]
    cy = (y0 + y1) / 2 - f.size * 0.62
    if number:
        draw.text(((x0 + x1 - ln.width) / 2, cy), ln.text, font=f, fill=ink.highlight)
    label = str(visual.get("label") or "")
    if label:
        lf = font(int(38 * u), 600)
        for i, l2 in enumerate(wrap(SCRATCH, label, lf, x1 - x0)[:2]):
            draw.text(((x0 + x1 - l2.width) / 2, cy + f.size * 1.06 + i * lf.size * 1.3), l2.text, font=lf, fill=ink.body)


def _bars(draw, box, visual, ink: Ink, u: float) -> None:
    """Horizontal bars — on a vertical frame they give the labels room to be read."""
    x0, y0, x1, y1 = box
    labels = [str(v) for v in (visual.get("labels") or [])]
    try:
        values = [float(v) for v in (visual.get("values") or [])]
    except (TypeError, ValueError):
        return
    if not values:
        return
    n = min(len(values), 6)
    values, labels = values[:n], (labels + [""] * n)[:n]
    unit = str(visual.get("unit") or "")
    title = str(visual.get("title") or "")
    vmax = max(abs(v) for v in values) or 1
    imax = max(range(n), key=lambda i: values[i])
    row, y0 = _pack((x0, y0 + (int(58 * u) if title else 0), x1, y1), n, 190 * u)
    if title:  # sits with the bars, not stranded above them
        small_caps(draw, (x0, y0 - int(52 * u)), title, int(30 * u), ink.faint)
    bar_h = min(row * 0.40, 66 * u)
    lf = font(int(30 * u), 600)
    vf = font(int(38 * u), 800)
    for i, v in enumerate(values):
        ry = y0 + i * row
        if labels[i]:
            draw.text((x0, ry), labels[i][:28].upper(), font=lf, fill=ink.body)
        by = ry + int(40 * u)
        full = x1 - x0
        w = max(int(6 * u), full * abs(v) / vmax)
        draw.rectangle([(x0, by), (x0 + full, by + bar_h)], fill=ink.rule)
        draw.rectangle([(x0, by), (x0 + w, by + bar_h)], fill=ink.highlight if i == imax else ink.accent)
        vt = f"{_abbrev(v)}{unit}"
        tw = draw.textlength(vt, font=vf)
        inside = w > tw + 40 * u
        draw.text((x0 + w - tw - int(20 * u) if inside else x0 + w + int(20 * u), by + bar_h / 2 - vf.size * 0.62), vt, font=vf, fill=ink.strong if not inside else (255, 255, 255))


def _contrast(draw, box, visual, ink: Ink, u: float) -> None:
    x0, y0, x1, y1 = box
    rows = [(visual.get("left") or {}, ink.accent), (visual.get("right") or {}, ink.highlight)]
    vals = []
    for d, _ in rows:
        try:
            vals.append(abs(float(str(d.get("value", 0)).replace(",", "").replace("$", "").replace("%", "") or 0)))
        except (TypeError, ValueError):
            vals.append(0.0)
    vmax = max(vals) or 1
    h, y0 = _pack((x0, y0, x1, y1), 2, 340 * u)
    for i, ((d, color), num) in enumerate(zip(rows, vals)):
        ry = y0 + i * h
        lf = font(int(32 * u), 700)
        draw.text((x0, ry), str(d.get("label", ""))[:28].upper(), font=lf, fill=ink.body)
        vf = font(int(96 * u), 800)
        draw.text((x0, ry + int(44 * u)), str(d.get("value", "")), font=vf, fill=color)
        by = ry + int(160 * u)
        draw.rectangle([(x0, by), (x1, by + int(14 * u))], fill=ink.rule)
        draw.rectangle([(x0, by), (x0 + (x1 - x0) * (num / vmax), by + int(14 * u))], fill=color)
        if i == 0:
            draw.line([(x0, ry + h - int(28 * u)), (x1, ry + h - int(28 * u))], fill=ink.rule, width=max(1, int(2 * u)))


def _timeline(draw, box, visual, ink: Ink, u: float) -> None:
    x0, y0, x1, y1 = box
    points = [p for p in (visual.get("points") or []) if isinstance(p, dict)][:5]
    if not points:
        return
    cx = x0 + int(13 * u)
    step, y0 = _pack((x0, y0, x1, y1), len(points), 210 * u)
    draw.line([(cx, y0 + int(18 * u)), (cx, y0 + int(18 * u) + step * (len(points) - 1))], fill=ink.rule, width=max(2, int(4 * u)))
    lf = font(int(36 * u), 800)
    tf = font(int(30 * u), 400)
    for i, p in enumerate(points):
        y = y0 + int(18 * u) + i * step
        r = int(15 * u)
        draw.ellipse([(cx - r, y - r), (cx + r, y + r)], fill=ink.highlight if i == len(points) - 1 else ink.accent)
        tx = cx + int(48 * u)
        draw.text((tx, y - int(24 * u)), str(p.get("label", ""))[:22], font=lf, fill=ink.strong)
        for k, ln in enumerate(wrap(SCRATCH, str(p.get("text", "")), tf, x1 - tx)[:2]):
            draw.text((tx, y + int(22 * u) + k * tf.size * 1.3), ln.text, font=tf, fill=ink.body)


def _list(draw, box, visual, ink: Ink, u: float) -> None:
    x0, y0, x1, y1 = box
    items = [str(i) for i in (visual.get("items") or [])][:5]
    if not items:
        return
    step, y0 = _pack((x0, y0, x1, y1), len(items), 175 * u)
    nf = font(int(34 * u), 800)
    bf = font(int(38 * u), 400)
    for i, item in enumerate(items):
        y = y0 + i * step
        draw.line([(x0, y), (x1, y)], fill=ink.rule, width=max(1, int(2 * u)))
        draw.text((x0, y + int(24 * u)), f"{i + 1:02d}", font=nf, fill=ink.highlight)
        tx = x0 + int(84 * u)
        for k, ln in enumerate(wrap(SCRATCH, item, bf, x1 - tx)[:2]):
            draw.text((tx, y + int(20 * u) + k * bf.size * 1.28), ln.text, font=bf, fill=ink.strong)


def _image(img, draw, box, visual, ink: Ink, pal: Palette, u: float, dark: bool) -> None:
    """Duotone the picture into the brand so a stock photo can't fight the palette."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    with PILImage.open(str(visual["path"])) as src:
        src = src.convert("RGB")
        scale = max(bw / src.width, bh / src.height)
        resized = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), PILImage.LANCZOS)
        left = (resized.width - bw) // 2
        top = (resized.height - bh) // 2
        crop = resized.crop((left, top, left + bw, top + bh))
    duo = ImageOps.colorize(ImageOps.autocontrast(crop.convert("L")), black=shade(pal.ink, 0.75), white=shade(pal.paper, 1.0), mid=pal.accent)
    img.paste(duo, (x0, y0))
    draw.rectangle([(x0, y0), (x1, y1)], outline=ink.rule, width=max(1, int(2 * u)))


# ---------------------------------------------------------------------------
# Text layer
# ---------------------------------------------------------------------------
def compose_text(scene: dict[str, Any], brand: dict[str, Any], *, width: int, height: int, index: int = 0, total: int = 1) -> PILImage.Image:
    pal = Palette.from_brand(brand)
    fr = Frame(width, height)
    role = role_for(scene, index, total)
    surf = surface_for(scene, index, total, role)
    base, dark = None, None
    from .design import surface_colors

    base, dark = surface_colors(pal, surf)
    if surf == "gradient":
        base = shade(base, 0.8)
    ink = ink_for(pal, base, dark)
    layer = PILImage.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    plan = _plan(scene, fr, role, index, total)
    if plan.head_lines:
        draw_lines(
            draw,
            plan.head_lines,
            plan.head_xy[0],
            plan.head_xy[1],
            plan.head_font,
            ink.strong,
            leading=plan.leading,
            align=plan.head_align,
            column=fr.column,
            emphasis=scene.get("emphasis") or [],
            emphasis_fill=ink.highlight,
        )
    if plan.body_lines:
        draw_lines(
            draw,
            plan.body_lines,
            plan.body_xy[0],
            plan.body_xy[1],
            plan.body_font,
            ink.body,
            leading=1.34,
            align=plan.body_align,
            column=fr.column if plan.body_align == "left" else fr.column * 0.92,
        )
    return layer


def counter_geometry(scene: dict[str, Any], brand: dict[str, Any], *, width: int, height: int, index: int = 0, total: int = 1) -> tuple[int, int, int] | None:
    """Where and how big the animated number is, so video and still agree."""
    role = role_for(scene, index, total)
    if role != "stat" and str(scene.get("visual_type") or "").lower() != "counter":
        return None
    fr = Frame(width, height)
    plan = _plan(scene, fr, role, index, total)
    if not plan.visual_box:
        return None
    x0, y0, x1, y1 = plan.visual_box
    visual = scene.get("visual") or {}
    try:
        value = float(visual.get("to", visual.get("value", 0)) or 0)
    except (TypeError, ValueError):
        value = 0.0
    text = f"{visual.get('prefix', '')}{_abbrev(value)}{visual.get('suffix', '')}"
    f, _ = fit(SCRATCH, text, x1 - x0, (y1 - y0) * 0.72, weight=800, start=int(300 * fr.unit), minimum=int(90 * fr.unit), leading=0.98, max_lines=1)
    return int((x0 + x1) / 2), int((y0 + y1) / 2 - f.size * 0.12), int(f.size)


def compose(scene: dict[str, Any], brand: dict[str, Any], *, width: int, height: int, index: int = 0, total: int = 1) -> PILImage.Image:
    base = compose_base(scene, brand, width=width, height=height, index=index, total=total)
    text = compose_text(scene, brand, width=width, height=height, index=index, total=total)
    base.paste(text, (0, 0), text)
    return base
