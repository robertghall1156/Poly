"""The visual design system for everything Poly renders: shorts, carousels, cards.

One place decides type, color, spacing and surface treatment, so a slide and a video
frame look like they came from the same publication. Nothing here hard-codes a color —
every value comes from the brand tokens in Settings.

The composition model is two layers:

  base(scene)  → RGB   surface + texture + furniture (kicker, index, rules, source) + data visual
  text(scene)  → RGBA  the headline and body only

The still preview composites them. The video renderer overlays the text layer with motion,
so the typography on screen is the same typography you saw in the editor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFilter, ImageFont

ASSET_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Archivo is the interface typeface; the renders use the same one so exports look like the app.
_WEIGHT_FILES = {400: "Archivo-Regular.ttf", 600: "Archivo-SemiBold.ttf", 700: "Archivo-Bold.ttf", 800: "Archivo-ExtraBold.ttf"}
_FALLBACKS = {
    800: ["/System/Library/Fonts/Supplemental/Arial Black.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    700: ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    600: ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    400: ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


@lru_cache(maxsize=256)
def font(size: int, weight: int = 400) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(8, int(size))
    weight = min(_WEIGHT_FILES, key=lambda w: abs(w - weight))
    vendored = ASSET_FONTS / _WEIGHT_FILES[weight]
    if vendored.exists():
        try:
            return ImageFont.truetype(str(vendored), size)
        except OSError:
            pass
    for p in _FALLBACKS[weight]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------
def hex_rgb(c: str, default: tuple[int, int, int] = (16, 42, 67)) -> tuple[int, int, int]:
    c = (c or "").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return default
    try:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except ValueError:
        return default


def mix(a: tuple, b: tuple, t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))  # type: ignore[return-value]


def shade(c: tuple, factor: float) -> tuple[int, int, int]:
    """factor < 1 darkens, > 1 lightens."""
    if factor <= 1:
        return mix(c, (0, 0, 0), 1 - factor)
    return mix(c, (255, 255, 255), min(1.0, factor - 1))


def _luma(c: tuple) -> float:
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255


@dataclass(frozen=True)
class Palette:
    ink: tuple
    paper: tuple
    accent: tuple
    highlight: tuple
    slate: tuple
    logo: str = ""

    @classmethod
    def from_brand(cls, brand: dict[str, Any]) -> Palette:
        return cls(
            ink=hex_rgb(brand.get("primary", "#102A43")),
            paper=hex_rgb(brand.get("background", "#F8F9FA"), (248, 249, 250)),
            accent=hex_rgb(brand.get("accent", "#0F766E"), (15, 118, 110)),
            highlight=hex_rgb(brand.get("highlight", "#C89B3C"), (200, 155, 60)),
            slate=hex_rgb(brand.get("muted", "#52667A"), (82, 102, 122)),
            logo=str(brand.get("logo_text", "") or ""),
        )


# surface name → (base color, is_dark)
def surface_colors(pal: Palette, name: str) -> tuple[tuple, bool]:
    table = {
        "paper": (pal.paper, False),
        "background": (pal.paper, False),
        "ink": (pal.ink, True),
        "primary": (pal.ink, True),
        "accent": (pal.accent, True),
        "gradient": (pal.ink, True),
    }
    base, _ = table.get(name, (pal.ink, True))
    return base, _luma(base) < 0.55


@dataclass(frozen=True)
class Ink:
    """Foreground colors resolved against a surface."""

    strong: tuple
    body: tuple
    faint: tuple
    rule: tuple
    accent: tuple
    highlight: tuple


def ink_for(pal: Palette, base: tuple, dark: bool) -> Ink:
    def readable(color: tuple, fallback: tuple) -> tuple:
        # a mark the same value as the surface it sits on is invisible
        return color if abs(_luma(color) - _luma(base)) >= 0.16 else fallback

    if dark:
        strong = mix(pal.paper, (255, 255, 255), 0.35)
        return Ink(
            strong=strong,
            body=mix(strong, base, 0.28),
            faint=mix(strong, base, 0.55),
            rule=mix(strong, base, 0.72),
            accent=readable(shade(pal.accent, 1.45), strong),
            highlight=readable(shade(pal.highlight, 1.15), strong),
        )
    return Ink(
        strong=pal.ink,
        body=mix(pal.ink, pal.slate, 0.55),
        faint=mix(pal.slate, base, 0.35),
        rule=mix(pal.slate, base, 0.72),
        accent=readable(pal.accent, pal.ink),
        highlight=readable(shade(pal.highlight, 0.92), pal.ink),
    )


# ---------------------------------------------------------------------------
# Surface treatment — flat fills look dead, so every surface gets depth
# ---------------------------------------------------------------------------
def _linear_gradient(top: tuple, bottom: tuple, w: int, h: int) -> PILImage.Image:
    strip = PILImage.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        px[0, y] = mix(top, bottom, y / max(1, h - 1))
    return strip.resize((w, h), PILImage.BILINEAR)


def _glow(img: PILImage.Image, center: tuple[float, float], radius: float, color: tuple, strength: float) -> None:
    """Soft radial light. Drawn small and upscaled — cheap and smooth."""
    w, h = img.size
    small_w, small_h = 96, int(96 * h / w)
    layer = PILImage.new("L", (small_w, small_h), 0)
    d = ImageDraw.Draw(layer)
    cx, cy = center[0] * small_w, center[1] * small_h
    r = radius * small_w
    steps = 26
    for i in range(steps, 0, -1):
        t = i / steps
        rr = r * t
        d.ellipse([(cx - rr, cy - rr), (cx + rr, cy + rr)], fill=int(255 * (1 - t) ** 1.6))
    layer = layer.resize((w, h), PILImage.BICUBIC).filter(ImageFilter.GaussianBlur(w * 0.02))
    tint = PILImage.new("RGB", (w, h), color)
    mask = layer.point(lambda v: int(v * strength))
    img.paste(tint, (0, 0), mask)


def _grain(img: PILImage.Image, amount: float = 0.028) -> PILImage.Image:
    """A whisper of noise. Kills the plasticky flatness of a pure digital fill."""
    if amount <= 0:
        return img
    w, h = img.size
    small = PILImage.effect_noise((max(2, w // 3), max(2, h // 3)), 42).convert("L")
    noise = small.resize((w, h), PILImage.BILINEAR)
    overlay = PILImage.merge("RGB", (noise, noise, noise))
    return PILImage.blend(img, overlay, amount)


def vertical_gradient(top: tuple, bottom: tuple, w: int, h: int) -> PILImage.Image:
    """Public alias — other renderers (memes, cards) build on the same gradient."""
    return _linear_gradient(top, bottom, w, h)


def surface(pal: Palette, name: str, w: int, h: int) -> tuple[PILImage.Image, tuple, bool]:
    base, dark = surface_colors(pal, name)
    if name == "gradient":
        img = _linear_gradient(shade(base, 1.12), shade(base, 0.45), w, h)
    elif dark:
        img = _linear_gradient(shade(base, 1.08), shade(base, 0.72), w, h)
        _glow(img, (0.82, 0.16), 0.55, shade(pal.accent, 1.25), 0.30)
        _glow(img, (0.10, 0.94), 0.60, shade(pal.ink, 0.5), 0.35)
    else:
        img = _linear_gradient(shade(base, 1.02), shade(base, 0.955), w, h)
        _glow(img, (0.88, 0.08), 0.5, shade(pal.accent, 1.85), 0.10)
    return _grain(img), base, dark


def hairline_grid(draw: ImageDraw.ImageDraw, w: int, h: int, margin: int, ink: Ink) -> None:
    """Faint structural rules — the page has bones even where it has no content."""
    for x in (margin, w - margin):
        draw.line([(x, 0), (x, h)], fill=ink.rule, width=1)


def corner_ticks(draw: ImageDraw.ImageDraw, box: tuple, color: tuple, size: int = 34, width: int = 4) -> None:
    x0, y0, x1, y1 = box
    for cx, cy, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        draw.line([(cx, cy), (cx + dx * size, cy)], fill=color, width=width)
        draw.line([(cx, cy), (cx, cy + dy * size)], fill=color, width=width)


# ---------------------------------------------------------------------------
# Type
# ---------------------------------------------------------------------------
@dataclass
class Line:
    text: str
    width: float
    words: list[tuple[float, float, str]]  # (x offset, width, word)


def _advance(draw, text: str, f, tracking: float) -> float:
    if not text:
        return 0.0
    return draw.textlength(text, font=f) + tracking * (len(text) - 1)


def draw_tracked(draw, xy, text: str, f, fill, tracking: float = 0.0) -> float:
    """Pillow has no letter-spacing. Small caps labels need it, so draw glyph by glyph."""
    if not tracking:
        draw.text(xy, text, font=f, fill=fill)
        return draw.textlength(text, font=f)
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + tracking
    return x - xy[0] - tracking


def wrap(draw, text: str, f, max_width: float, tracking: float = 0.0) -> list[Line]:
    """Word wrap that also records where each word sits, so words can be emphasized in place.
    Splits words that are themselves wider than the column, so text can never bleed off frame."""
    out: list[Line] = []
    space = draw.textlength(" ", font=f) + tracking
    for para in (text or "").split("\n"):
        words: list[str] = []
        for w in para.split():
            if _advance(draw, w, f, tracking) <= max_width:
                words.append(w)
                continue
            chunk = ""
            for ch in w:  # hard-split an over-long token rather than overflow
                if _advance(draw, chunk + ch, f, tracking) > max_width and chunk:
                    words.append(chunk)
                    chunk = ch
                else:
                    chunk += ch
            if chunk:
                words.append(chunk)
        cur: list[tuple[float, float, str]] = []
        x = 0.0
        for w in words:
            ww = _advance(draw, w, f, tracking)
            if cur and x + ww > max_width:
                out.append(Line(" ".join(t[2] for t in cur), x - space, cur))
                cur, x = [], 0.0
            cur.append((x, ww, w))
            x += ww + space
        out.append(Line(" ".join(t[2] for t in cur), max(0.0, x - space), cur))
    return [ln for ln in out if ln.text] or [Line("", 0.0, [])]


def fit(draw, text: str, max_width: float, max_height: float, *, weight: int = 800, start: int = 96, minimum: int = 40, leading: float = 1.06, tracking: float = 0.0, max_lines: int = 6):
    """Largest size at which the text fits the box. Returns (font, lines)."""
    words = [w for w in re.split(r"\s+", text or "") if w]
    size = start
    while size >= minimum:
        f = font(size, weight)
        # a word wider than the column would be split mid-word — shrink instead
        if words and max(_advance(draw, w, f, tracking) for w in words) > max_width:
            size -= 3
            continue
        lines = wrap(draw, text, f, max_width, tracking)
        if len(lines) <= max_lines and len(lines) * size * leading <= max_height:
            return f, lines
        size -= 3
    f = font(minimum, weight)
    return f, wrap(draw, text, f, max_width, tracking)[:max_lines]


def draw_lines(draw, lines: list[Line], x: float, y: float, f, fill, *, leading: float = 1.06, tracking: float = 0.0, align: str = "left", column: float = 0.0, emphasis: list[str] | None = None, emphasis_fill=None, slab=None) -> float:
    """Draw wrapped lines; returns the y below the block. Emphasized words are recolored
    in place (and optionally sit on a solid slab, the way a broadcast graphic marks a term)."""
    terms = [re.sub(r"[^\w'’-]", "", str(t)).lower() for t in (emphasis or []) if str(t).strip()]
    step = f.size * leading
    for ln in lines:
        ox = 0.0 if align == "left" else (column - ln.width) / 2 if align == "center" else column - ln.width
        for wx, ww, word in ln.words:
            key = re.sub(r"[^\w'’-]", "", word).lower()
            hot = bool(key) and any(key == t or (len(t) > 3 and t in key) for t in terms)
            px, py = x + ox + wx, y
            if hot and slab is not None:
                pad = f.size * 0.14
                draw.rectangle([(px - pad, py + f.size * 0.06), (px + ww + pad, py + f.size * 1.02)], fill=slab)
            color = (emphasis_fill if hot and emphasis_fill is not None else fill)
            draw_tracked(draw, (px, py), word, f, color, tracking)
        y += step
    return y


def small_caps(draw, xy, text: str, size: int, fill, tracking: float | None = None) -> float:
    f = font(size, 700)
    return draw_tracked(draw, xy, (text or "").upper(), f, fill, size * 0.14 if tracking is None else tracking)


# ---------------------------------------------------------------------------
# Headline hygiene
# ---------------------------------------------------------------------------
_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "is", "it", "of", "on", "or", "the", "to", "vs", "with"}


def clean_headline(text: str) -> str:
    """Models produce things like 'THE APOLogy'. Repair mangled casing without flattening
    genuine acronyms (GDP, ICE, NATO) or hyphenated names."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return text

    def fix(tok: str) -> str:
        core = tok.strip("“”\"'()[].,:;!?—-")
        if not core or not any(c.isalpha() for c in core):
            return tok
        if core.isupper() or core.islower():
            return tok  # consistently cased — leave it alone
        letters = [c for c in core if c.isalpha()]
        # mixed case that isn't Capitalised and isn't camel-ish → rebuild it
        if core[0].isupper() and core[1:].islower():
            return tok
        upper_ratio = sum(c.isupper() for c in letters) / len(letters)
        if 0.2 < upper_ratio < 1.0:
            return tok.replace(core, core.capitalize())
        return tok

    tokens = [fix(t) for t in text.split(" ")]
    out = " ".join(tokens)
    if out.isupper():  # ALL CAPS input: keep it, the layouts set their own case
        return out
    # Title Case the result when the source was clearly trying to
    caps = sum(1 for t in tokens if t[:1].isupper())
    if len(tokens) > 1 and caps >= max(2, len(tokens) - 2):
        out = " ".join(t if i and t.lower() in _SMALL else (t[:1].upper() + t[1:] if t[:1].isalpha() else t) for i, t in enumerate(tokens))
    return out


def sentence(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


# Glyphs the text faces don't carry render as blank boxes. Substitute or drop them,
# and tell the caller when an arrow was meant so it can draw a real one.
_GLYPHS = {
    "→": "", "➔": "", "➡": "", "⮕": "", "▶": "", "➜": "", "⇒": "",
    "←": "", "⬅": "", "◀": "",
    "✓": "", "✔": "", "✗": "", "✘": "", "❌": "", "⭐": "",
    "…": "...", " ": " ", "‑": "-", "‒": "-", "―": "—",
}
_ARROWS = "→➔➡⮕▶➜⇒"


def sanitize(text: str) -> tuple[str, bool]:
    """Returns (renderable text, had a forward arrow)."""
    raw = text or ""
    arrow = any(c in raw for c in _ARROWS)
    for bad, good in _GLYPHS.items():
        raw = raw.replace(bad, good)
    raw = "".join(c for c in raw if c == "\n" or ord(c) < 0x2100)
    return re.sub(r"[ \t]+", " ", raw).strip(), arrow


# ---------------------------------------------------------------------------
# Roles — what kind of slide is this, and how should it be composed
# ---------------------------------------------------------------------------
ROLES = ["cover", "point", "stat", "chart", "contrast", "quote", "list", "timeline", "image", "symbol", "question", "closer"]

_VISUAL_ROLE = {
    "chart": "chart",
    "comparison": "contrast",
    "counter": "stat",
    "timeline": "timeline",
    "list": "list",
    "image": "image",
    "quote": "quote",
    "symbol": "symbol",
    "question": "question",
    "title": "cover",
}


def role_for(scene: dict[str, Any], index: int, total: int) -> str:
    explicit = str(scene.get("role") or "").strip().lower()
    if explicit in ROLES:
        return explicit
    vt = str(scene.get("visual_type") or "text").lower()
    role = _VISUAL_ROLE.get(vt)
    if role:
        return role
    if index == 0:
        return "cover"
    # a headline that asks something is a question card wherever it falls
    if str(scene.get("on_screen_text") or "").strip().endswith("?"):
        return "question"
    if total > 1 and index == total - 1:
        return "closer"
    return "point"


# Surfaces rotate through a deck so six slides are never six of the same thing.
_RHYTHM = ["ink", "paper", "paper", "accent", "paper", "ink"]


def surface_for(scene: dict[str, Any], index: int, total: int, role: str) -> str:
    """A surface a person chose in the editor wins. Otherwise the deck decides: the role sets
    the tone and the rhythm keeps consecutive slides from looking the same."""
    named = {"primary": "ink", "background": "paper"}.get(str(scene.get("background") or "").strip().lower(), str(scene.get("background") or "").strip().lower())
    if scene.get("surface_locked") and named in ("ink", "paper", "accent", "gradient"):
        return named
    if role == "cover":
        return "gradient"
    if role in ("stat", "quote", "question"):
        return "ink"
    if role == "closer":
        return "accent"
    return _RHYTHM[index % len(_RHYTHM)]
