"""Faceless video rendering: VideoScene list → real 1080×1920 MP4. Fully local.

Pipeline:
1. (optional) synthesize narration per scene with local TTS; stretch scene durations to fit speech
2. draw each scene's background + data visual (chart/comparison/counter base/timeline/list/quote/image) with Pillow using brand tokens
3. animate on-screen text with an ASS subtitle track per scene (fade / slide_up / pop / typewriter, emphasis words in the highlight color; counters animate numerically)
4. FFmpeg: still + subtle zoom + ASS burn → per-scene clip; concat; mux narration + optional music bed
Carousels reuse the same scene drawing at 1080×1350 and export PNGs + a ZIP.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFilter
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import VideoProject
from ..providers.tts.local import pick_tts
from . import settings as settings_service
from .images import _fit_font, _font, _hex, _wrap

W, H = 1080, 1920
SAFE_X, SAFE_TOP, SAFE_BOTTOM = 90, 170, 200
FPS = 30


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
def load_brand(db: Session, project: VideoProject | None = None) -> dict[str, Any]:
    brand = dict(settings_service.get(db, "brand", {}) or {})
    if project is not None:
        brand.update({k: v for k, v in (project.brand_overrides or {}).items() if v})
    return brand


def _bg_color(brand: dict, name: str) -> tuple:
    table = {"primary": brand.get("primary", "#102A43"), "background": brand.get("background", "#F8F9FA"), "accent": brand.get("accent", "#0F766E")}
    return _hex(table.get(name, brand.get("primary", "#102A43")))


def _text_color_for(brand: dict, bg: str) -> str:
    return brand.get("text_on_light", "#102A43") if bg == "background" else brand.get("text_on_dark", "#F8F9FA")


def _hex_to_ass(hex_color: str) -> str:
    h = (hex_color or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


# ---------------------------------------------------------------------------
# Scene background drawing (everything except the animated main text)
# ---------------------------------------------------------------------------
def draw_scene_background(scene: dict[str, Any], brand: dict, *, width: int = W, height: int = H, for_carousel: bool = False) -> PILImage.Image:
    bg = scene.get("background", "primary")
    base = _bg_color(brand, bg)
    if bg == "gradient":
        img = _vertical_gradient(_hex(brand.get("primary", "#102A43")), _darken(_hex(brand.get("primary", "#102A43")), 0.55), width, height)
    else:
        img = PILImage.new("RGB", (width, height), base)
        # subtle vignette so flat colors don't look dead
        img = _vertical_gradient(base, _darken(base, 0.88), width, height) if bg != "background" else img
    draw = ImageDraw.Draw(img)
    accent = _hex(brand.get("accent", "#0F766E"))
    gold = _hex(brand.get("highlight", "#C89B3C"))
    fg = _hex(_text_color_for(brand, bg))
    muted = tuple(int(a * 0.62 + b * 0.38) for a, b in zip(fg, base))

    vt = scene.get("visual_type", "text")
    visual = scene.get("visual") or {}
    area = (SAFE_X, int(height * 0.40), width - SAFE_X, height - int(height * 0.24))  # visual band
    if vt == "chart" and visual.get("values"):
        _draw_chart(draw, area, visual, fg, accent, gold, muted)
    elif vt == "comparison" and visual.get("left"):
        _draw_comparison(draw, area, visual, fg, accent, gold, base)
    elif vt == "timeline" and visual.get("points"):
        _draw_timeline(draw, area, visual, fg, accent, muted)
    elif vt == "list" and visual.get("items"):
        _draw_list(draw, area, visual, fg, accent)
    elif vt == "quote":
        draw.rectangle([(SAFE_X, area[1]), (SAFE_X + 10, area[3])], fill=accent)
    elif vt == "image" and visual.get("path") and Path(str(visual["path"])).exists():
        _paste_image(img, area, str(visual["path"]))
        if visual.get("generated"):
            _label(draw, (SAFE_X, area[3] + 8), "AI-generated image", muted)
    elif vt == "counter":
        # number itself is animated in ASS; draw the label plate
        label = str(visual.get("label", ""))
        if label:
            f = _font(40)
            tw = draw.textlength(label, font=f)
            draw.text(((width - tw) / 2, int(height * 0.60)), label, font=f, fill=muted)
    # accent tick under the text zone for title/question scenes
    if vt in ("title", "question") and not for_carousel:
        draw.rectangle([(width / 2 - 70, int(height * 0.62)), (width / 2 + 70, int(height * 0.62) + 8)], fill=gold if vt == "question" else accent)

    src = scene.get("source") or visual.get("source") or ""
    if src:
        _label(draw, (SAFE_X, height - SAFE_BOTTOM + 90), f"Source: {src}", muted)
    logo = brand.get("logo_text", "")
    if logo:
        f = _font(30)
        draw.text((width - SAFE_X - draw.textlength(logo, font=f), SAFE_TOP - 90), logo, font=f, fill=muted)
    return img


def _label(draw, xy, text, color):
    draw.text(xy, text, font=_font(28), fill=color)


def _vertical_gradient(top, bottom, width, height):
    img = PILImage.new("RGB", (1, height))
    for y in range(height):
        t = y / max(1, height - 1)
        img.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img.resize((width, height))


def _darken(color, factor):
    return tuple(int(c * factor) for c in color)


def _draw_chart(draw, area, visual, fg, accent, gold, muted):
    x0, y0, x1, y1 = area
    labels = [str(v) for v in visual.get("labels", [])][:8]
    try:
        values = [float(v) for v in visual.get("values", [])][: len(labels) or 8]
    except (TypeError, ValueError):
        return
    if not values:
        return
    title = str(visual.get("title", ""))
    unit = str(visual.get("unit", ""))
    if title:
        f = _font(40)
        draw.text((x0, y0 - 60), title, font=f, fill=fg)
    n = len(values)
    vmax = max(abs(v) for v in values) or 1
    gap = (x1 - x0) / n
    bw = gap * 0.58
    bottom = y1 - 60
    top = y0 + 20
    imax = max(range(n), key=lambda i: values[i])
    for i, v in enumerate(values):
        h = (bottom - top) * abs(v) / vmax
        bx = x0 + i * gap + (gap - bw) / 2
        draw.rounded_rectangle([(bx, bottom - h), (bx + bw, bottom)], radius=10, fill=gold if i == imax else accent)
        vf = _font(34)
        vt = f"{v:,.0f}{unit}" if abs(v) >= 10 else f"{v:,.1f}{unit}"
        draw.text((bx + bw / 2 - draw.textlength(vt, font=vf) / 2, bottom - h - 46), vt, font=vf, fill=fg)
        if i < len(labels):
            lf = _font(30)
            for k, line in enumerate(_wrap(draw, labels[i], lf, int(gap * 0.9))[:2]):
                draw.text((bx + bw / 2 - draw.textlength(line, font=lf) / 2, bottom + 14 + k * 34), line, font=lf, fill=muted)
    draw.line([(x0, bottom), (x1, bottom)], fill=muted, width=3)


def _draw_comparison(draw, area, visual, fg, accent, gold, base):
    x0, y0, x1, y1 = area
    mid = (x0 + x1) / 2
    for side, box, color in (("left", (x0, y0 + 30, mid - 18, y1 - 60), accent), ("right", (mid + 18, y0 + 30, x1, y1 - 60), gold)):
        d = visual.get(side) or {}
        draw.rounded_rectangle(box, radius=26, fill=_darken(color, 0.25), outline=color, width=4)
        val = str(d.get("value", ""))
        lab = str(d.get("label", ""))
        vf, vlines = _fit_font(draw, val, int(box[2] - box[0] - 60), int((y1 - y0) * 0.4), start=110, minimum=40)
        ty = (box[1] + box[3]) / 2 - vf.size * len(vlines) * 0.65
        for line in vlines:
            draw.text(((box[0] + box[2]) / 2 - draw.textlength(line, font=vf) / 2, ty), line, font=vf, fill=fg)
            ty += vf.size * 1.2
        lf = _font(34)
        for k, line in enumerate(_wrap(draw, lab, lf, int(box[2] - box[0] - 60))[:2]):
            draw.text(((box[0] + box[2]) / 2 - draw.textlength(line, font=lf) / 2, box[3] - 100 + k * 38), line, font=lf, fill=fg)
    vs = _font(44)
    draw.text((mid - draw.textlength("vs", font=vs) / 2, (y0 + y1) / 2 - 30), "vs", font=vs, fill=fg)


def _draw_timeline(draw, area, visual, fg, accent, muted):
    x0, y0, x1, y1 = area
    points = [p for p in visual.get("points", []) if isinstance(p, dict)][:5]
    if not points:
        return
    cx = x0 + 40
    draw.line([(cx, y0 + 20), (cx, y1 - 20)], fill=accent, width=6)
    step = (y1 - y0 - 60) / max(1, len(points) - 1) if len(points) > 1 else 0
    for i, p in enumerate(points):
        y = y0 + 30 + i * step
        draw.ellipse([(cx - 14, y - 14), (cx + 14, y + 14)], fill=accent)
        lf = _font(36)
        draw.text((cx + 40, y - 24), str(p.get("label", ""))[:24], font=lf, fill=fg)
        tf = _font(30)
        for k, line in enumerate(_wrap(draw, str(p.get("text", "")), tf, int(x1 - cx - 60))[:2]):
            draw.text((cx + 40, y + 18 + k * 34), line, font=tf, fill=muted)


def _draw_list(draw, area, visual, fg, accent):
    x0, y0, x1, y1 = area
    items = [str(i) for i in visual.get("items", [])][:5]
    y = y0 + 10
    body = _font(40)
    for i, item in enumerate(items, 1):
        draw.ellipse([(x0, y + 6), (x0 + 46, y + 52)], fill=accent)
        nf = _font(30)
        draw.text((x0 + 23 - draw.textlength(str(i), font=nf) / 2, y + 12), str(i), font=nf, fill="white")
        for line in _wrap(draw, item, body, int(x1 - x0 - 80))[:2]:
            draw.text((x0 + 70, y), line, font=body, fill=fg)
            y += 50
        y += 26
        if y > y1:
            break


def _paste_image(img, area, path):
    x0, y0, x1, y1 = area
    with PILImage.open(path) as src:
        src = src.convert("RGB")
        scale = min((x1 - x0) / src.width, (y1 - y0) / src.height)
        nw, nh = int(src.width * scale), int(src.height * scale)
        resized = src.resize((nw, nh))
        shadow = PILImage.new("RGB", (nw + 24, nh + 24), (0, 0, 0))
        img.paste(shadow.filter(ImageFilter.GaussianBlur(1)), (int((x0 + x1 - nw) / 2) - 12, int((y0 + y1 - nh) / 2) - 8))
        img.paste(resized, (int((x0 + x1 - nw) / 2), int((y0 + y1 - nh) / 2)))


# ---------------------------------------------------------------------------
# ASS text animation
# ---------------------------------------------------------------------------
def _ts(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int((t % 3600) // 60):02d}:{t % 60:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def _emphasize(text: str, emphasis: list[str], gold_ass: str) -> str:
    out = _esc(text)
    for w in emphasis or []:
        w = _esc(str(w)).strip()
        if not w:
            continue
        out = re.sub(re.escape(w), f"{{\\\\c{gold_ass}}}{w}{{\\\\r}}", out, count=1, flags=re.IGNORECASE)
    return out


def build_scene_ass(scene: dict[str, Any], brand: dict, *, width: int = W, height: int = H) -> str:
    dur = float(scene.get("duration", 3))
    bg = scene.get("background", "primary")
    fg_ass = _hex_to_ass(_text_color_for(brand, bg))
    gold_ass = _hex_to_ass(brand.get("highlight", "#C89B3C"))
    vt = scene.get("visual_type", "text")
    has_visual = vt in ("chart", "comparison", "counter", "timeline", "list", "image")
    big_size = 92 if vt in ("title", "question") else (58 if has_visual else 72)
    # text position: centered for title/question/plain text; top band when a visual occupies the middle
    align, mv = (5, 0) if not has_visual else (8, SAFE_TOP + 40)
    font = brand.get("font") or "Arial"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Big,{font},{big_size},{fg_ass},&H000000FF,&H00000000,&H60000000,-1,0,0,0,100,100,0,0,1,0,1,{align},{SAFE_X},{SAFE_X},{mv},1
Style: Sub,{font},44,{fg_ass},&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,0,0,{align},{SAFE_X},{SAFE_X},{mv},1
Style: Counter,{font},150,{fg_ass},&H000000FF,&H00000000,&H60000000,-1,0,0,0,100,100,0,0,1,0,1,5,{SAFE_X},{SAFE_X},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: list[str] = []
    text = scene.get("on_screen_text", "")
    anim = scene.get("animation", "fade")
    body = _emphasize(text, scene.get("emphasis", []), gold_ass)
    cy = height // 2 if not has_visual else mv
    if text:
        if anim == "typewriter":
            words = text.split()
            step = min(0.28, max(0.10, (dur * 0.5) / max(1, len(words))))
            for i in range(len(words)):
                shown = " ".join(words[: i + 1])
                start, end = i * step, ((i + 1) * step if i < len(words) - 1 else dur)
                lines.append(f"Dialogue: 2,{_ts(start)},{_ts(end)},Big,,0,0,0,,{_emphasize(shown, scene.get('emphasis', []), gold_ass)}")
        else:
            fx = {
                "fade": "{\\fad(280,200)}",
                "slide_up": f"{{\\move({width // 2},{cy + 110},{width // 2},{cy},0,380)\\fad(220,0)}}" if not has_visual else "{\\fad(280,200)}",
                "pop": "{\\fad(120,0)\\t(0,150,\\fscx116\\fscy116)\\t(150,320,\\fscx100\\fscy100)}",
                "none": "",
            }.get(anim, "{\\fad(280,200)}")
            lines.append(f"Dialogue: 2,{_ts(0)},{_ts(dur)},Big,,0,0,0,,{fx}{body}")
    sub = scene.get("subtext", "")
    if sub:
        off = int(big_size * 1.9)
        lines.append(f"Dialogue: 1,{_ts(min(0.5, dur / 4))},{_ts(dur)},Sub,,0,0,{mv + off if has_visual else 0},,{{\\fad(250,180)\\an{align}\\pos({width // 2},{(cy + off) if not has_visual else mv + off})}}{_esc(sub)}")
    if vt == "counter":
        lines += _counter_events(scene, dur, gold_ass, height)
    return header + "\n".join(lines) + "\n"


def _counter_events(scene, dur, gold_ass, height):
    v = scene.get("visual") or {}
    try:
        start_v, end_v = float(v.get("from", 0)), float(v.get("to", 0))
    except (TypeError, ValueError):
        return []
    prefix, suffix = str(v.get("prefix", "")), str(v.get("suffix", ""))
    steps = 36
    t_anim = min(1.8, dur * 0.6)
    out = []
    cy = int(height * 0.52)
    for i in range(steps + 1):
        t0 = (i / steps) * t_anim
        t1 = ((i + 1) / steps) * t_anim if i < steps else dur
        p = 1 - (1 - i / steps) ** 3  # ease-out
        val = start_v + (end_v - start_v) * p
        label = f"{prefix}{_abbrev(val)}{suffix}"
        color = f"{{\\c{gold_ass}}}" if i == steps else ""
        out.append(f"Dialogue: 3,{_ts(t0)},{_ts(t1)},Counter,,0,0,0,,{{\\an5\\pos(540,{cy})}}{color}{label}")
    return out


def _abbrev(v: float) -> str:
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.1f}B".replace(".0B", "B")
    if a >= 1e6:
        return f"{v / 1e6:.1f}M".replace(".0M", "M")
    if a >= 1e4:
        return f"{v / 1e3:.0f}K"
    return f"{v:,.0f}"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-600:]}")


def render_scene_preview(db: Session, project: VideoProject, index: int, *, scale: float = 0.35) -> Path:
    """Static PNG preview of one scene (background + text drawn in place) for the editor."""
    scenes = project.scenes or []
    if not 0 <= index < len(scenes):
        raise ValueError("scene index out of range")
    scene = scenes[index]
    brand = load_brand(db, project)
    img = draw_scene_background(scene, brand)
    draw = ImageDraw.Draw(img)
    vt = scene.get("visual_type", "text")
    has_visual = vt in ("chart", "comparison", "counter", "timeline", "list", "image")
    fg = _hex(_text_color_for(brand, scene.get("background", "primary")))
    text = scene.get("on_screen_text", "")
    if text:
        size = 92 if vt in ("title", "question") else (58 if has_visual else 72)
        f, lines = _fit_font(draw, text, W - 2 * SAFE_X, int(H * 0.3), start=size, minimum=34)
        y = (H / 2 - len(lines) * f.size * 0.65) if not has_visual else SAFE_TOP + 40
        for line in lines:
            draw.text(((W - draw.textlength(line, font=f)) / 2, y), line, font=f, fill=fg)
            y += f.size * 1.25
        sub = scene.get("subtext", "")
        if sub:
            sf = _font(44)
            draw.text(((W - draw.textlength(sub, font=sf)) / 2, y + 14), sub, font=sf, fill=fg)
    if vt == "counter":
        v = scene.get("visual") or {}
        label = f"{v.get('prefix', '')}{_abbrev(float(v.get('to', 0) or 0))}{v.get('suffix', '')}"
        cf = _font(150)
        draw.text(((W - draw.textlength(label, font=cf)) / 2, H * 0.52 - 75), label, font=cf, fill=_hex(brand.get("highlight", "#C89B3C")))
    out = get_settings().cache_path / f"scene-{project.id}-{index}.png"
    if scale != 1.0:
        img = img.resize((int(W * scale), int(H * scale)))
    img.save(out)
    return out


def render_project(db: Session, project: VideoProject, *, progress=None) -> VideoProject:
    if project.kind == "carousel":
        return render_carousel(db, project, progress=progress)
    cfg = get_settings()
    scenes = [dict(s) for s in (project.scenes or [])]
    if not scenes:
        raise ValueError("no scenes to render")
    brand = load_brand(db, project)
    voice_cfg = settings_service.get(db, "voice", {}) or {}
    use_tts = project.voice_mode == "tts"
    project.render_status = "rendering"
    db.commit()
    tmp = Path(tempfile.mkdtemp(prefix="poly-faceless-"))
    try:
        # 1) narration first (durations may stretch)
        narration_wavs: list[str | None] = []
        if use_tts:
            tts = pick_tts(voice_cfg.get("engine", "auto"), voice_cfg.get("piper_model", ""))
            for i, s in enumerate(scenes):
                if progress:
                    progress(0.05 + 0.15 * i / len(scenes), f"Voiceover scene {i + 1}")
                if s.get("narration"):
                    wav = str(tmp / f"vo{i}.wav")
                    d = tts.synthesize(s["narration"], wav, voice=project.tts_voice or voice_cfg.get("voice", ""), rate=int(voice_cfg.get("rate", 180)))
                    s["duration"] = round(max(float(s["duration"]), d + 0.35), 2)
                    narration_wavs.append(wav)
                else:
                    narration_wavs.append(None)
        else:
            narration_wavs = [None] * len(scenes)

        # 2+3) per-scene clips
        clip_paths = []
        for i, s in enumerate(scenes):
            if progress:
                progress(0.2 + 0.5 * i / len(scenes), f"Rendering scene {i + 1}/{len(scenes)}")
            bg_png = tmp / f"bg{i}.png"
            draw_scene_background(s, brand).save(bg_png)
            ass_path = tmp / f"s{i}.ass"
            ass_path.write_text(build_scene_ass(s, brand), encoding="utf-8")
            dur = float(s["duration"])
            frames = max(2, int(dur * FPS))
            ass_esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
            vf = (
                f"scale={int(W * 1.08)}:{int(H * 1.08)},"
                f"zoompan=z='min(1.06,1+0.0009*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
                f"ass='{ass_esc}',format=yuv420p"
            )
            if s.get("transition") == "fade":
                fade_d = min(0.35, dur / 4)
                vf += f",fade=t=in:st=0:d={fade_d:.2f},fade=t=out:st={dur - fade_d:.2f}:d={fade_d:.2f}"
            clip = tmp / f"clip{i}.mp4"
            _run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.2f}", "-i", str(bg_png),
                  "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", str(FPS), str(clip)])
            clip_paths.append(clip)

        # 4) concat video
        if progress:
            progress(0.75, "Assembling")
        concat_list = tmp / "list.txt"
        concat_list.write_text("".join(f"file '{p}'\n" for p in clip_paths))
        silent = tmp / "video.mp4"
        _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(silent)])

        # audio track: narration segments padded to scene durations, optional music bed
        audio_out = None
        if any(narration_wavs) or project.music_path:
            segs = []
            for i, s in enumerate(scenes):
                seg = tmp / f"a{i}.wav"
                dur = float(s["duration"])
                if narration_wavs[i]:
                    _run(["ffmpeg", "-y", "-v", "error", "-i", narration_wavs[i], "-af", f"apad,atrim=0:{dur:.2f}", "-ar", "24000", "-ac", "1", str(seg)])
                else:
                    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{dur:.2f}", str(seg)])
                segs.append(seg)
            alist = tmp / "alist.txt"
            alist.write_text("".join(f"file '{p}'\n" for p in segs))
            voice_track = tmp / "voice.wav"
            _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(alist), "-c", "copy", str(voice_track)])
            audio_out = voice_track
            if project.music_path and Path(project.music_path).exists():
                mixed = tmp / "mixed.wav"
                total = sum(float(s["duration"]) for s in scenes)
                _run(["ffmpeg", "-y", "-v", "error", "-i", str(voice_track), "-stream_loop", "-1", "-i", project.music_path,
                      "-filter_complex", f"[1:a]volume=0.14,atrim=0:{total:.2f}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[out]",
                      "-map", "[out]", str(mixed)])
                audio_out = mixed

        stem = re.sub(r"[^a-z0-9]+", "-", (project.content_item.title or "faceless").lower()).strip("-")[:50] or "faceless"
        out_path = cfg.renders_path / f"{stem}-{project.id[:8]}.mp4"
        if audio_out is not None:
            _run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(audio_out), "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_path)])
        else:
            _run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-c", "copy", "-movflags", "+faststart", str(out_path)])

        project.scenes = scenes  # persist stretched durations
        project.render_path = str(out_path)
        project.render_status = "done"
        project.render_error = None
        item = project.content_item
        if item.status in ("IDEA", "SCRIPTING"):
            item.status = "EDITING"
        db.commit()
        return project
    except Exception as e:
        project.render_status = "failed"
        project.render_error = str(e)[:1000]
        db.commit()
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Carousel
# ---------------------------------------------------------------------------
CAROUSEL_W, CAROUSEL_H = 1080, 1350


def render_carousel(db: Session, project: VideoProject, *, progress=None) -> VideoProject:
    cfg = get_settings()
    scenes = project.scenes or []
    if not scenes:
        raise ValueError("no slides to render")
    brand = load_brand(db, project)
    project.render_status = "rendering"
    db.commit()
    out_dir = cfg.renders_path / f"carousel-{project.id[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        paths = []
        for i, s in enumerate(scenes):
            if progress:
                progress(0.1 + 0.8 * i / len(scenes), f"Slide {i + 1}/{len(scenes)}")
            img = draw_scene_background(s, brand, width=CAROUSEL_W, height=CAROUSEL_H, for_carousel=True)
            draw = ImageDraw.Draw(img)
            fg = _hex(_text_color_for(brand, s.get("background", "primary")))
            heading = s.get("on_screen_text", "")
            body = s.get("subtext", "") or (s.get("narration", "") if s.get("visual_type") not in ("chart", "comparison", "timeline", "list") else "")
            is_title = s.get("visual_type") in ("title", "question")
            y = CAROUSEL_H * (0.42 if is_title else 0.12)
            if heading:
                f, lines = _fit_font(draw, heading, CAROUSEL_W - 2 * SAFE_X, int(CAROUSEL_H * 0.3), start=84 if is_title else 64, minimum=36)
                for line in lines:
                    draw.text((SAFE_X if not is_title else (CAROUSEL_W - draw.textlength(line, font=f)) / 2, y), line, font=f, fill=fg)
                    y += f.size * 1.25
                y += 24
            if body:
                bf = _font(42)
                for line in _wrap(draw, body, bf, CAROUSEL_W - 2 * SAFE_X)[:10]:
                    draw.text((SAFE_X, y), line, font=bf, fill=fg)
                    y += 56
            footer = (s.get("visual") or {}).get("footer", "")
            if footer:
                draw.text((SAFE_X, CAROUSEL_H - 70), footer, font=_font(30), fill=_hex(brand.get("highlight", "#C89B3C")))
            nf = _font(30)
            page = f"{i + 1}/{len(scenes)}"
            draw.text((CAROUSEL_W - SAFE_X - draw.textlength(page, font=nf), CAROUSEL_H - 70), page, font=nf, fill=_hex(brand.get("highlight", "#C89B3C")))
            p = out_dir / f"slide-{i + 1:02d}.png"
            img.save(p)
            paths.append(p)
        zip_path = out_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in paths:
                z.write(p, p.name)
        project.render_path = str(zip_path)
        project.render_status = "done"
        project.render_error = None
        item = project.content_item
        if item.status in ("IDEA", "SCRIPTING"):
            item.status = "EDITING"
        db.commit()
        return project
    except Exception as e:
        project.render_status = "failed"
        project.render_error = str(e)[:1000]
        db.commit()
        raise
