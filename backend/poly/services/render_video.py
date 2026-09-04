"""Faceless video rendering: VideoScene list → real 1080×1920 MP4. Fully local.

Pipeline:
1. (optional) synthesize narration per scene with local TTS; stretch scene durations to fit speech
2. compose each scene with the design system (poly.services.render_scene) into two layers —
   a background plate (surface, furniture, data visual) and an RGBA text layer
3. FFmpeg: a slow push-in on the plate with the text layer overlaid on its own motion
   (fade / rise / pop), so the type on screen is the same type the editor showed
4. concat the scene clips; mux narration and an optional music bed

A counting number is the one thing a still can't do, so counter scenes keep a small ASS
pass over the composed frame. Carousels reuse the same composition at 1080×1350.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import VideoProject
from ..providers.tts.local import pick_tts
from . import settings as settings_service
from .render_scene import compose, compose_base, compose_text, counter_geometry

W, H = 1080, 1920
CAROUSEL_W, CAROUSEL_H = 1080, 1350
FPS = 30


def geometry(project: VideoProject | None) -> tuple[int, int]:
    """A carousel slide is 4:5, a short is 9:16 — previews have to match what gets exported."""
    if project is not None and project.kind in ("carousel", "graphic"):
        return CAROUSEL_W, CAROUSEL_H
    return W, H


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
def load_brand(db: Session, project: VideoProject | None = None) -> dict[str, Any]:
    brand = dict(settings_service.get(db, "brand", {}) or {})
    if project is not None:
        brand.update({k: v for k, v in (project.brand_overrides or {}).items() if v})
    return brand


def draw_scene_background(scene: dict[str, Any], brand: dict, *, width: int = W, height: int = H, index: int = 0, total: int = 1, animate_counter: bool = False):
    """The scene plate. Composition itself lives in render_scene."""
    return compose_base(scene, brand, width=width, height=height, index=index, total=total, animate_counter=animate_counter)


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------
def text_motion(animation: str, height: int) -> tuple[str, str]:
    """(alpha filter for the text layer, overlay y expression).

    The design system draws the type, so motion only has to move and reveal it.
    'typewriter' maps to a rise: a per-word reveal costs a render pass per word and
    reads worse than a clean entrance at this length.
    """
    rise = int(height * 0.035)
    if animation == "none":
        return "", "0"
    if animation == "pop":
        return "fade=t=in:st=0:d=0.14:alpha=1", f"'if(lt(t,0.22), -{max(6, rise // 4)}*sin(t/0.22*3.14159), 0)'"
    if animation in ("slide_up", "rise", "typewriter"):
        return "fade=t=in:st=0:d=0.30:alpha=1", f"'if(lt(t,0.42), (1-t/0.42)*{rise}, 0)'"
    return "fade=t=in:st=0:d=0.32:alpha=1", "0"


def scene_filter(scene: dict[str, Any], *, width: int, height: int, frames: int, duration: float, ass_path: str | None = None) -> str:
    """The whole per-scene filter graph. Split out so it can be read and tested."""
    alpha, y_expr = text_motion(str(scene.get("animation") or "fade"), height)
    graph = (
        # A gentle drift, deliberately small: the plate carries rules and bars that sit close
        # to the frame edge, and a heavier push-in would crop them.
        f"[0:v]scale={int(width * 1.03)}:{int(height * 1.03)},"
        f"zoompan=z='min(1.025,1+0.0004*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={FPS}[bg];"
        "[1:v]format=rgba" + (f",{alpha}" if alpha else "") + "[tx];"
        f"[bg][tx]overlay=x=0:y={y_expr}[v0];"
    )
    tail = "[v0]"
    if ass_path:
        graph += f"[v0]ass='{ass_path}'[v1];"
        tail = "[v1]"
    chain = "format=yuv420p"
    if scene.get("transition") == "fade":
        fade_d = min(0.35, duration / 4)
        chain = f"fade=t=in:st=0:d={fade_d:.2f},fade=t=out:st={duration - fade_d:.2f}:d={fade_d:.2f},{chain}"
    return graph + f"{tail}{chain}[v]"


# ---------------------------------------------------------------------------
# Counter animation (the only text ffmpeg has to draw itself)
# ---------------------------------------------------------------------------
def _hex_to_ass(hex_color: str) -> str:
    h = (hex_color or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _ts(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int((t % 3600) // 60):02d}:{t % 60:05.2f}"


def _abbrev(v: float) -> str:
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.1f}B".replace(".0B", "B")
    if a >= 1e6:
        return f"{v / 1e6:.1f}M".replace(".0M", "M")
    if a >= 1e4:
        return f"{v / 1e3:.0f}K"
    return f"{v:,.0f}" if abs(v) >= 10 else f"{v:,.1f}"


def build_counter_ass(scene: dict[str, Any], brand: dict, *, width: int = W, height: int = H, index: int = 0, total: int = 1) -> str | None:
    """A number ticking up into place, positioned exactly where the still draws it."""
    geo = counter_geometry(scene, brand, width=width, height=height, index=index, total=total)
    if geo is None:
        return None
    cx, cy, size = geo
    v = scene.get("visual") or {}
    try:
        start_v = float(v.get("from", 0) or 0)
        end_v = float(v.get("to", v.get("value", 0)) or 0)
    except (TypeError, ValueError):
        return None
    prefix, suffix = str(v.get("prefix", "")), str(v.get("suffix", ""))
    gold = _hex_to_ass(brand.get("highlight", "#C89B3C"))
    dur = float(scene.get("duration", 3) or 3)
    font = brand.get("font") or "Archivo"
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Counter,{font},{size},{gold},&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    steps = 36
    t_anim = min(1.8, dur * 0.6)
    lines = []
    for i in range(steps + 1):
        t0 = (i / steps) * t_anim
        t1 = ((i + 1) / steps) * t_anim if i < steps else dur
        p = 1 - (1 - i / steps) ** 3  # ease-out
        label = f"{prefix}{_abbrev(start_v + (end_v - start_v) * p)}{suffix}"
        lines.append(f"Dialogue: 3,{_ts(t0)},{_ts(t1)},Counter,,0,0,0,,{{\\an5\\pos({cx},{cy})}}{label}")
    return header + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-600:]}")


def render_scene_preview(db: Session, project: VideoProject, index: int, *, scale: float = 0.35) -> Path:
    """Still preview of one scene, at the geometry it will actually be exported in.

    Cached on the scene's own content: composing a slide costs the better part of a second
    (gradient, grain, duotone), and an editor asks for every thumbnail at once. Re-rendering
    each time left the rail empty for ten seconds, which reads as broken rather than slow.
    The key is a hash of the scene and the brand, so an edit invalidates it by itself.
    """
    scenes = project.scenes or []
    if not 0 <= index < len(scenes):
        raise ValueError("scene index out of range")
    width, height = geometry(project)
    brand = load_brand(db, project)
    key = hashlib.sha1(
        json.dumps({"scene": scenes[index], "brand": brand, "n": len(scenes)}, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    out = get_settings().cache_path / f"scene-{project.id}-{index}-{width}x{height}-{int(scale * 100)}-{key}.png"
    if out.exists():
        return out
    img = compose(scenes[index], brand, width=width, height=height, index=index, total=len(scenes))
    if scale != 1.0:
        img = img.resize((int(width * scale), int(height * scale)))
    img.save(out)
    for stale in out.parent.glob(f"scene-{project.id}-{index}-*.png"):
        if stale != out:
            stale.unlink(missing_ok=True)  # one file per scene per size, not a growing pile
    return out


def render_project(db: Session, project: VideoProject, *, progress=None) -> VideoProject:
    if project.kind == "carousel":
        return render_carousel(db, project, progress=progress)
    cfg = get_settings()
    scenes = [dict(s) for s in (project.scenes or [])]
    if not scenes:
        raise ValueError("no scenes to render")
    count = len(scenes)
    brand = load_brand(db, project)
    voice_cfg = settings_service.get(db, "voice", {}) or {}
    use_tts = project.voice_mode == "tts"
    project.render_status = "rendering"
    db.commit()
    tmp = Path(tempfile.mkdtemp(prefix="poly-faceless-"))
    try:
        # 1) narration first, since it stretches durations
        narration_wavs: list[str | None] = []
        if use_tts:
            tts = pick_tts(voice_cfg.get("engine", "auto"), voice_cfg.get("piper_model", ""))
            for i, s in enumerate(scenes):
                if progress:
                    progress(0.05 + 0.15 * i / count, f"Voiceover scene {i + 1}")
                if s.get("narration"):
                    wav = str(tmp / f"vo{i}.wav")
                    d = tts.synthesize(s["narration"], wav, voice=project.tts_voice or voice_cfg.get("voice", ""), rate=int(voice_cfg.get("rate", 180)))
                    s["duration"] = round(max(float(s["duration"]), d + 0.35), 2)
                    narration_wavs.append(wav)
                else:
                    narration_wavs.append(None)
        else:
            narration_wavs = [None] * count

        # 2+3) compose and render each scene
        clip_paths = []
        for i, s in enumerate(scenes):
            if progress:
                progress(0.2 + 0.5 * i / count, f"Rendering scene {i + 1}/{count}")
            ass = build_counter_ass(s, brand, width=W, height=H, index=i, total=count)
            bg_png = tmp / f"bg{i}.png"
            tx_png = tmp / f"tx{i}.png"
            compose_base(s, brand, width=W, height=H, index=i, total=count, animate_counter=ass is not None).save(bg_png)
            compose_text(s, brand, width=W, height=H, index=i, total=count).save(tx_png)
            ass_arg = None
            if ass:
                ass_file = tmp / f"c{i}.ass"
                ass_file.write_text(ass, encoding="utf-8")
                ass_arg = str(ass_file).replace("\\", "/").replace(":", "\\:")
            dur = float(s["duration"])
            frames = max(2, int(dur * FPS))
            clip = tmp / f"clip{i}.mp4"
            _run(["ffmpeg", "-y", "-v", "error",
                  "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.2f}", "-i", str(bg_png),
                  "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.2f}", "-i", str(tx_png),
                  "-filter_complex", scene_filter(s, width=W, height=H, frames=frames, duration=dur, ass_path=ass_arg),
                  "-map", "[v]", "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", str(FPS), str(clip)])
            clip_paths.append(clip)

        # 4) concat video
        if progress:
            progress(0.75, "Assembling")
        concat_list = tmp / "list.txt"
        concat_list.write_text("".join(f"file '{p}'\n" for p in clip_paths))
        silent = tmp / "video.mp4"
        _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(silent)])

        # audio: narration padded to scene durations, optional music bed under it
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
                total_s = sum(float(s["duration"]) for s in scenes)
                _run(["ffmpeg", "-y", "-v", "error", "-i", str(voice_track), "-stream_loop", "-1", "-i", project.music_path,
                      "-filter_complex", f"[1:a]volume=0.14,atrim=0:{total_s:.2f}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[out]",
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
            img = compose(s, brand, width=CAROUSEL_W, height=CAROUSEL_H, index=i, total=len(scenes))
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
