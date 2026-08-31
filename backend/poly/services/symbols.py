"""Symbolic editorial graphics — the concept drawn, rather than a photo fetched.

For a lot of political stories the honest picture doesn't exist and a stock photo is filler.
A struck-through place name with a new one stamped over it says "he renamed the lake" faster
and more truthfully than any photograph of a man at a desk.

Every mark is deterministic Pillow drawing over the brand palette, so it needs no network,
no model, and carries no licensing risk. Marks take their words from the scene.
"""
from __future__ import annotations

import math
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw

from .design import Ink, Palette, fit, font, mix, small_caps, wrap

SYMBOLS = ["rename", "stamp", "plaque", "seal", "scale", "signature"]

SCRATCH = ImageDraw.Draw(PILImage.new("RGB", (8, 8)))


def draw_symbol(img: PILImage.Image, box: tuple[int, int, int, int], spec: dict[str, Any], ink: Ink, pal: Palette, u: float) -> bool:
    """Draw the named mark into `box`. Returns False if the spec can't be drawn."""
    name = str(spec.get("symbol") or "").strip().lower()
    fn = {
        "rename": _rename,
        "stamp": _stamp,
        "plaque": _plaque,
        "seal": _seal,
        "scale": _scale,
        "signature": _signature,
    }.get(name)
    if fn is None:
        return False
    try:
        fn(img, ImageDraw.Draw(img), box, spec, ink, pal, u)
        return True
    except (ValueError, TypeError, KeyError):
        return False


def _rotated(img: PILImage.Image, size: tuple[int, int], angle: float, paint, at: tuple[int, int]) -> None:
    """Draw on a transparent layer, rotate it, paste it. Pillow can't rotate a draw call."""
    layer = PILImage.new("RGBA", size, (0, 0, 0, 0))
    paint(ImageDraw.Draw(layer))
    rot = layer.rotate(angle, expand=True, resample=PILImage.BICUBIC)
    img.paste(rot, (at[0] - (rot.width - size[0]) // 2, at[1] - (rot.height - size[1]) // 2), rot)


# ---------------------------------------------------------------------------
def _rename(img, draw, box, spec, ink: Ink, pal: Palette, u: float) -> None:
    """OLD NAME struck out, NEW NAME stamped over it. The renaming device."""
    x0, y0, x1, y1 = box
    old = str(spec.get("old") or spec.get("from") or "").strip()
    new = str(spec.get("new") or spec.get("to") or "").strip()
    if not (old and new):
        raise ValueError("rename needs old and new")
    w = x1 - x0
    cy = (y0 + y1) / 2

    of, olines = fit(SCRATCH, old, w, (y1 - y0) * 0.30, weight=700, start=int(96 * u), minimum=int(40 * u), leading=1.04, max_lines=2)
    oy = cy - (y1 - y0) * 0.30
    for ln in olines:
        lx = x0 + (w - ln.width) / 2
        draw.text((lx, oy), ln.text, font=of, fill=ink.faint)
        # the strike sits on the x-height, hand-drawn weight, slightly overshooting the word
        sy = oy + of.size * 0.58
        draw.line([(lx - int(14 * u), sy + int(4 * u)), (lx + ln.width + int(14 * u), sy - int(3 * u))], fill=ink.highlight, width=max(3, int(9 * u)))
        oy += of.size * 1.04

    # a short downward tick, then the new name stamped askew
    mid = oy + int(30 * u)
    draw.line([(x0 + w / 2, mid), (x0 + w / 2, mid + int(46 * u))], fill=ink.rule, width=max(2, int(4 * u)))

    nf, nlines = fit(SCRATCH, new, w * 0.86, (y1 - y0) * 0.30, weight=800, start=int(110 * u), minimum=int(46 * u), leading=1.0, max_lines=2)
    tw = int(max(ln.width for ln in nlines) + 70 * u)
    th = int(len(nlines) * nf.size * 1.0 + 56 * u)

    def paint(d):
        d.rectangle([(0, 0), (tw - 1, th - 1)], outline=ink.highlight, width=max(3, int(7 * u)))
        d.rectangle([(int(10 * u), int(10 * u)), (tw - int(11 * u), th - int(11 * u))], outline=ink.highlight, width=max(1, int(2 * u)))
        ty = int(28 * u)
        for ln in nlines:
            d.text(((tw - ln.width) / 2, ty), ln.text, font=nf, fill=ink.highlight)
            ty += nf.size

    _rotated(img, (tw, th), -4.5, paint, (int(x0 + (w - tw) / 2), int(mid + 60 * u)))


def _stamp(img, draw, box, spec, ink: Ink, pal: Palette, u: float) -> None:
    """A word stamped in a double-ruled box, set askew — an official act, marked."""
    x0, y0, x1, y1 = box
    text = str(spec.get("text") or spec.get("word") or "").strip().upper()
    if not text:
        raise ValueError("stamp needs text")
    w = x1 - x0
    f, lines = fit(SCRATCH, text, w * 0.78, (y1 - y0) * 0.42, weight=800, start=int(120 * u), minimum=int(44 * u), leading=1.0, max_lines=2, tracking=int(6 * u))
    bw = int(max(ln.width for ln in lines) + 90 * u)
    bh = int(len(lines) * f.size * 1.05 + 70 * u)
    color = ink.highlight

    def paint(d):
        d.rectangle([(0, 0), (bw - 1, bh - 1)], outline=color, width=max(4, int(9 * u)))
        d.rectangle([(int(14 * u), int(14 * u)), (bw - int(15 * u), bh - int(15 * u))], outline=color, width=max(1, int(3 * u)))
        ty = int(35 * u)
        for ln in lines:
            x = (bw - ln.width) / 2
            for ch in ln.text:
                d.text((x, ty), ch, font=f, fill=color)
                x += d.textlength(ch, font=f) + int(6 * u)
            ty += f.size * 1.05

    _rotated(img, (bw, bh), -7, paint, (int(x0 + (w - bw) / 2), int((y0 + y1) / 2 - bh / 2)))


def _plaque(img, draw, box, spec, ink: Ink, pal: Palette, u: float) -> None:
    """An engraved nameplate. A name fixed to a thing that wasn't named after anyone."""
    x0, y0, x1, y1 = box
    name = str(spec.get("text") or spec.get("name") or "").strip().upper()
    if not name:
        raise ValueError("plaque needs text")
    w = x1 - x0
    pw, ph = int(w * 0.9), int(min((y1 - y0) * 0.5, 320 * u))
    px, py = int(x0 + (w - pw) / 2), int((y0 + y1) / 2 - ph / 2)
    plate = mix(pal.highlight, pal.ink, 0.30)
    draw.rectangle([(px, py), (px + pw, py + ph)], fill=plate)
    draw.rectangle([(px, py), (px + pw, py + int(6 * u))], fill=mix(pal.highlight, (255, 255, 255), 0.45))  # bevel
    draw.rectangle([(px, py + ph - int(6 * u)), (px + pw, py + ph)], fill=mix(plate, (0, 0, 0), 0.35))
    draw.rectangle([(px + int(20 * u), py + int(20 * u)), (px + pw - int(20 * u), py + ph - int(20 * u))], outline=mix(plate, (0, 0, 0), 0.30), width=max(1, int(3 * u)))
    for cx in (px + int(40 * u), px + pw - int(40 * u)):
        for cy2 in (py + int(38 * u), py + ph - int(38 * u)):
            r = int(9 * u)
            draw.ellipse([(cx - r, cy2 - r), (cx + r, cy2 + r)], fill=mix(plate, (0, 0, 0), 0.45))
    f, lines = fit(SCRATCH, name, pw - int(120 * u), ph - int(90 * u), weight=800, start=int(76 * u), minimum=int(32 * u), leading=1.05, max_lines=2, tracking=int(5 * u))
    ty = py + (ph - len(lines) * f.size * 1.05) / 2
    engraved = mix(plate, (0, 0, 0), 0.55)
    for ln in lines:
        x = px + (pw - ln.width) / 2
        for ch in ln.text:
            draw.text((x, ty + max(1, int(2 * u))), ch, font=f, fill=mix(plate, (255, 255, 255), 0.30))  # highlight below
            draw.text((x, ty), ch, font=f, fill=engraved)
            x += draw.textlength(ch, font=f) + int(5 * u)
        ty += f.size * 1.05


def _seal(img, draw, box, spec, ink: Ink, pal: Palette, u: float) -> None:
    """A ring seal with words around it — the look of an order, without faking a real one."""
    x0, y0, x1, y1 = box
    ring_text = str(spec.get("text") or "EXECUTIVE ORDER").strip().upper()
    center_text = str(spec.get("center") or "").strip().upper()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = int(min(x1 - x0, y1 - y0) * 0.42)
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=ink.highlight, width=max(3, int(7 * u)))
    inner = int(r * 0.80)
    draw.ellipse([(cx - inner, cy - inner), (cx + inner, cy + inner)], outline=ink.highlight, width=max(1, int(2 * u)))
    for i in range(36):  # milled edge
        a = i * math.tau / 36
        draw.line([(cx + math.cos(a) * r, cy + math.sin(a) * r), (cx + math.cos(a) * (r + int(12 * u)), cy + math.sin(a) * (r + int(12 * u)))], fill=ink.highlight, width=max(1, int(3 * u)))
    f = font(int(30 * u), 700)
    span = math.pi * 0.95
    start = math.pi / 2 + span / 2
    for i, ch in enumerate(ring_text):
        a = start - (span * i / max(1, len(ring_text) - 1))
        rr = r * 0.89
        _rotated(img, (int(46 * u), int(46 * u)), math.degrees(a) - 90,
                 lambda d, ch=ch: d.text((int(23 * u) - d.textlength(ch, font=f) / 2, int(8 * u)), ch, font=f, fill=ink.highlight),
                 (int(cx + math.cos(a) * rr - 23 * u), int(cy - math.sin(a) * rr - 23 * u)))
    if center_text:
        cf, lines = fit(SCRATCH, center_text, inner * 1.5, inner, weight=800, start=int(64 * u), minimum=int(26 * u), leading=1.05, max_lines=3)
        ty = cy - len(lines) * cf.size * 0.52
        for ln in lines:
            draw.text((cx - ln.width / 2, ty), ln.text, font=cf, fill=ink.strong)
            ty += cf.size * 1.05


def _scale(img, draw, box, spec, ink: Ink, pal: Palette, u: float) -> None:
    """A balance that actually tips — the beam is weighted by the two values."""
    x0, y0, x1, y1 = box
    left = spec.get("left") or {}
    right = spec.get("right") or {}
    if not (left and right):
        raise ValueError("scale needs left and right")

    def weight(d):
        try:
            return abs(float(str(d.get("value", 1)).replace(",", "").strip("$% ").split()[0]))
        except (TypeError, ValueError, IndexError):
            return 1.0

    w, h = x1 - x0, y1 - y0
    lw, rw = weight(left), weight(right)
    tilt = 0.0 if lw == rw else max(-1.0, min(1.0, (lw - rw) / max(lw, rw, 1e-6))) * 0.22

    cx = (x0 + x1) / 2
    pivot_y = y0 + h * 0.34
    arm = w * 0.34
    drop = h * 0.16
    pan_w = w * 0.15
    base_y = y1 - h * 0.10

    # stand: column from the base up to the pivot, on a plinth
    draw.line([(cx, pivot_y), (cx, base_y)], fill=ink.rule, width=max(3, int(9 * u)))
    draw.line([(cx - w * 0.13, base_y), (cx + w * 0.13, base_y)], fill=ink.rule, width=max(3, int(10 * u)))

    # beam
    lx, ly = cx - arm, pivot_y + arm * tilt
    rx, ry = cx + arm, pivot_y - arm * tilt
    draw.line([(lx, ly), (rx, ry)], fill=ink.strong, width=max(4, int(11 * u)))
    r = int(13 * u)
    draw.ellipse([(cx - r, pivot_y - r), (cx + r, pivot_y + r)], fill=ink.strong)

    lf = font(int(29 * u), 700)
    vf = font(int(52 * u), 800)
    for (px, py), d, color in (((lx, ly), left, ink.accent), ((rx, ry), right, ink.highlight)):
        pan_y = py + drop
        draw.line([(px, py), (px, pan_y)], fill=ink.rule, width=max(2, int(4 * u)))
        # a shallow bowl: the lower half of a wide ellipse
        draw.arc([(px - pan_w, pan_y - pan_w * 0.34), (px + pan_w, pan_y + pan_w * 0.62)], 0, 180, fill=color, width=max(4, int(11 * u)))
        draw.line([(px - pan_w, pan_y + int(2 * u)), (px + pan_w, pan_y + int(2 * u))], fill=color, width=max(2, int(5 * u)))

        value = str(d.get("value", ""))
        if value:
            draw.text((px - draw.textlength(value, font=vf) / 2, py - vf.size * 1.5), value, font=vf, fill=color)
        label = str(d.get("label", ""))[:26].upper()
        ty = pan_y + pan_w * 0.72 + int(20 * u)
        for ln in wrap(SCRATCH, label, lf, pan_w * 2.4)[:2]:
            draw.text((px - ln.width / 2, ty), ln.text, font=lf, fill=ink.body)
            ty += lf.size * 1.25


def _signature(img, draw, box, spec, ink: Ink, pal: Palette, u: float) -> None:
    """A signature over a ruled line: something was signed. Deliberately an abstract scrawl —
    it is not, and must not resemble, any real person's actual signature."""
    x0, y0, x1, y1 = box
    caption = str(spec.get("text") or "Signed by executive order").strip()
    w = x1 - x0
    cy = (y0 + y1) / 2
    pts = []
    seed = sum(ord(c) for c in caption) or 7
    for i in range(140):
        t = i / 139
        x = x0 + w * 0.12 + t * w * 0.76
        y = cy - math.sin(t * math.pi * 3.1 + seed % 5) * (y1 - y0) * 0.11 - math.sin(t * math.pi * 11) * (y1 - y0) * 0.025 + t * (y1 - y0) * 0.05
        pts.append((x, y))
    for i in range(len(pts) - 1):
        width = max(2, int((10 - 6 * abs(0.5 - i / len(pts)) * 2) * u))
        draw.line([pts[i], pts[i + 1]], fill=ink.strong, width=width)
    ly = cy + (y1 - y0) * 0.20
    draw.line([(x0 + w * 0.08, ly), (x1 - w * 0.08, ly)], fill=ink.rule, width=max(1, int(3 * u)))
    small_caps(draw, (x0 + w * 0.08, ly + int(22 * u)), caption[:44], int(26 * u), ink.faint)


def describe(spec: dict[str, Any]) -> str:
    """One line for the editor, so the owner knows what the mark will say."""
    name = str(spec.get("symbol") or "")
    if name == "rename":
        return f"{spec.get('old', '?')} struck through → {spec.get('new', '?')} stamped"
    if name in ("stamp", "plaque"):
        return f"{name}: {spec.get('text', '')}"
    if name == "seal":
        return f"seal: {spec.get('text', 'EXECUTIVE ORDER')}"
    if name == "scale":
        return f"balance: {(spec.get('left') or {}).get('label', '')} vs {(spec.get('right') or {}).get('label', '')}"
    if name == "signature":
        return f"signature: {spec.get('text', '')}"
    return name


__all__ = ["SYMBOLS", "draw_symbol", "describe", "wrap"]
