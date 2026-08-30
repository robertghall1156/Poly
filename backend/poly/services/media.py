"""Video library: indexing (metadata only), transcription, clip discovery, 9:16 rendering.

All processing is local (FFmpeg + local Whisper). Source files are never modified or copied;
renders go to `data/renders/`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Clip, Story, TranscriptSegment, Video, VideoFolder
from ..providers.base import ProviderError
from ..providers.registry import Router
from . import settings as settings_service
from .llm_utils import as_list, as_str, chat_json
from .search import embed_entity
from .topics import tag_topics

log = logging.getLogger(__name__)
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts", ".m2ts"}


def _ffmpeg() -> str:
    return get_settings().ffmpeg_path


def _ffprobe() -> str:
    return get_settings().ffprobe_path


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------
def probe(path: str) -> dict[str, Any]:
    cmd = [_ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr[-300:]}")
    data = json.loads(proc.stdout or "{}")
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    fps = 0.0
    if v.get("avg_frame_rate") and v["avg_frame_rate"] != "0/0":
        num, den = v["avg_frame_rate"].split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    return {
        "duration": float(fmt.get("duration") or v.get("duration") or 0.0),
        "width": int(v.get("width") or 0),
        "height": int(v.get("height") or 0),
        "fps": round(fps, 3),
        "codec": v.get("codec_name", ""),
        "has_audio": a is not None,
        "size_bytes": int(fmt.get("size") or 0),
        "creation_time": (fmt.get("tags") or {}).get("creation_time"),
    }


def _fingerprint(path: Path, size: int) -> str:
    h = hashlib.sha1()
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
    return h.hexdigest()


def add_folder(db: Session, path: str, *, recursive: bool = True) -> VideoFolder:
    p = Path(os.path.expanduser(path)).resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"{p} is not a directory")
    row = db.execute(select(VideoFolder).where(VideoFolder.path == str(p))).scalar_one_or_none()
    if row is None:
        row = VideoFolder(path=str(p), recursive=recursive)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def scan_folder(db: Session, folder: VideoFolder, *, progress=None) -> dict[str, int]:
    root = Path(folder.path)
    if not root.is_dir():
        raise FileNotFoundError(folder.path)
    it = root.rglob("*") if folder.recursive else root.glob("*")
    files = [f for f in it if f.is_file() and f.suffix.lower() in VIDEO_EXT and not f.name.startswith(".")]
    existing = {v.path: v for v in folder.videos}
    stats = {"found": len(files), "added": 0, "updated": 0, "missing": 0}
    seen = set()
    for i, f in enumerate(files):
        if progress:
            progress(i / max(1, len(files)), f.name)
        seen.add(str(f))
        st = f.stat()
        row = existing.get(str(f))
        if row is not None and row.size_bytes == st.st_size and row.file_modified_at and abs(row.file_modified_at.timestamp() - st.st_mtime) < 2:
            row.missing = False
            continue
        try:
            meta = probe(str(f))
        except RuntimeError as e:
            log.warning("probe failed for %s: %s", f, e)
            continue
        created = datetime.fromtimestamp(getattr(st, "st_birthtime", st.st_ctime), tz=UTC)
        if row is None:
            row = Video(folder_id=folder.id, path=str(f), filename=f.name)
            db.add(row)
            stats["added"] += 1
        else:
            stats["updated"] += 1
            row.transcript_status = "none"  # file changed → transcript stale
        row.size_bytes = st.st_size
        row.duration = meta["duration"]
        row.width, row.height, row.fps, row.codec, row.has_audio = meta["width"], meta["height"], meta["fps"], meta["codec"], meta["has_audio"]
        row.file_created_at = created
        row.file_modified_at = datetime.fromtimestamp(st.st_mtime, tz=UTC)
        row.indexed_at = datetime.now(UTC)
        row.fingerprint = _fingerprint(f, st.st_size)
        row.missing = False
    for path, row in existing.items():
        if path not in seen:
            row.missing = True
            stats["missing"] += 1
    folder.last_scanned_at = datetime.now(UTC)
    folder.file_count = len(files)
    db.commit()
    db.refresh(folder)
    for v in folder.videos:
        embed_entity(db, "video", v)
    return stats


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
def extract_audio(video_path: str, out_wav: str) -> str:
    cmd = [_ffmpeg(), "-y", "-v", "error", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", out_wav]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"audio extraction failed: {proc.stderr[-300:]}")
    return out_wav


def transcribe_video(db: Session, video: Video, *, router: Router | None = None, progress=None) -> Video:
    router = router or Router(db)
    media_cfg = settings_service.get(db, "media", {}) or {}
    picked = router.transcription(media_cfg.get("transcription_mode", "auto"))
    if picked is None:
        video.transcript_status = "failed"
        video.transcript_error = "No local transcription runtime available. Install mlx-whisper (Apple Silicon) or faster-whisper — see Settings → Local AI."
        db.commit()
        raise ProviderError(video.transcript_error, provider="transcription", retryable=True)
    provider, model = picked
    if media_cfg.get("transcription_model"):
        model = media_cfg["transcription_model"]
    video.transcript_status = "running"
    video.transcript_provider = f"{provider.name}:{model}"
    db.commit()
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "audio.wav")
        if progress:
            progress(0.05, "Extracting audio")
        extract_audio(video.path, wav)
        if progress:
            progress(0.15, f"Transcribing with {provider.name} ({model})")
        try:
            result = provider.transcribe(wav, model=model)
        except ProviderError as e:
            video.transcript_status = "failed"
            video.transcript_error = str(e)
            db.commit()
            raise
    save_transcript(db, video, [{"start": s.start, "end": s.end, "text": s.text, "words": [{"w": w.word, "s": w.start, "e": w.end} for w in s.words]} for s in result.segments], language=result.language, provider=video.transcript_provider)
    if progress:
        progress(0.8, "Summarising")
    try:
        summarize_video(db, video, router)
    except Exception as e:  # summary is optional
        log.warning("video summary failed: %s", e)
    return video


def save_transcript(db: Session, video: Video, segments: list[dict[str, Any]], *, language: str = "en", provider: str = "import") -> Video:
    db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video.id).delete()
    for i, s in enumerate(segments):
        db.add(TranscriptSegment(video_id=video.id, idx=i, start=float(s["start"]), end=float(s["end"]), text=str(s.get("text", "")).strip(), words=s.get("words") or []))
    video.transcript_status = "done"
    video.transcript_language = language
    video.transcript_provider = provider
    video.transcript_error = None
    db.commit()
    db.refresh(video)
    for seg in video.segments:
        embed_entity(db, "transcript_segment", seg)
    return video


SYSTEM_VIDEO = """You summarise a transcript for the owner's own video library. Return JSON:
{summary (2-3 sentences), topics (list of short topics), people (list of people mentioned by name), key_moments (list of {t (seconds), label})}.
Use only what is in the transcript."""


def summarize_video(db: Session, video: Video, router: Router) -> None:
    text = "\n".join(f"[{s.start:.0f}s] {s.text}" for s in video.segments)[:14000]
    if not text.strip():
        return
    try:
        data, _ = chat_json(router, "FAST", "video_summary", SYSTEM_VIDEO, text, max_tokens=800)
        video.summary = as_str(data.get("summary"))
        video.topics = [as_str(t) for t in as_list(data.get("topics"))][:10]
        video.people = [as_str(t) for t in as_list(data.get("people"))][:20]
        video.key_moments = [m for m in as_list(data.get("key_moments")) if isinstance(m, dict)][:20]
    except (ProviderError, ValueError):
        video.topics = tag_topics(text)
    db.commit()
    embed_entity(db, "video", video, router)


# ---------------------------------------------------------------------------
# Clip discovery
# ---------------------------------------------------------------------------
HOOK_PAT = re.compile(r"\b(here's why|here is why|the truth is|most people|nobody|no one|what if|why does|why do|the problem is|the real reason|let me explain|think about|imagine|question)\b|\?", re.I)
SURPRISE_PAT = re.compile(r"\b(actually|surprising|turns out|contrary|counterintuitive|nobody talks about|secret|shocking|wrong)\b", re.I)
EDU_PAT = re.compile(r"\b(because|means|works|system|incentive|the way|in other words|for example|history|how it)\b", re.I)
ENERGY_PAT = re.compile(r"!|\b(never|always|huge|massive|crazy|insane|absolutely|really)\b", re.I)
ARGUMENT_PAT = re.compile(r"\b(so|therefore|which means|that's why|the point is|my view|i think|i believe|should|we need)\b", re.I)
CONTROVERSY_PAT = re.compile(r"\b(both parties|democrats|republicans|congress|billionaire|corporat|union|tax|immigra|pentagon|ceo)\w*", re.I)
MIN_CLIP, MAX_CLIP, TARGET = 18.0, 75.0, 45.0


def _sentences(segments: list[TranscriptSegment]) -> list[dict[str, Any]]:
    """Merge segments into sentence-ish units with start/end."""
    units = []
    buf, start, end = [], None, None
    for s in segments:
        if not s.text.strip():
            continue
        if start is None:
            start = s.start
        buf.append(s.text.strip())
        end = s.end
        if re.search(r"[.!?]$", s.text.strip()) or (end - start) > 15:
            units.append({"start": start, "end": end, "text": " ".join(buf)})
            buf, start = [], None
    if buf and start is not None:
        units.append({"start": start, "end": end, "text": " ".join(buf)})
    return units


def score_window(text: str, duration: float, *, news_keywords: set[str] | None = None) -> dict[str, float]:
    words = max(1, len(text.split()))
    first = " ".join(text.split()[:14])
    hook = min(1.0, 0.35 + 0.35 * len(HOOK_PAT.findall(first)) + 0.15 * len(SURPRISE_PAT.findall(first)))
    self_contained = 1.0 if re.search(r"[.!?]$", text.strip()) else 0.5
    if len(text) < 120:
        self_contained *= 0.6
    energy = min(1.0, 0.3 + 0.12 * len(ENERGY_PAT.findall(text)) + 0.2 * (words / max(duration, 1) > 2.6))
    clarity = min(1.0, max(0.2, 1.1 - abs(words / max(1, len(re.findall(r"[.!?]", text)) or 1) - 16) / 30))
    surprise = min(1.0, 0.2 + 0.25 * len(SURPRISE_PAT.findall(text)))
    educational = min(1.0, 0.2 + 0.12 * len(EDU_PAT.findall(text)))
    argument = min(1.0, 0.2 + 0.15 * len(ARGUMENT_PAT.findall(text)))
    controversy = min(1.0, 0.1 + 0.15 * len(CONTROVERSY_PAT.findall(text)))
    relevance = 0.0
    if news_keywords:
        toks = set(re.findall(r"[a-z]{4,}", text.lower()))
        relevance = min(1.0, len(toks & news_keywords) / 6)
    length = 1.0 - min(1.0, abs(duration - TARGET) / TARGET)
    total = 0.2 * hook + 0.15 * self_contained + 0.1 * energy + 0.12 * clarity + 0.08 * surprise + 0.13 * educational + 0.1 * argument + 0.05 * controversy + 0.07 * relevance
    total = round(total * (0.7 + 0.3 * length), 3)
    return {"hook": round(hook, 2), "self_contained": round(self_contained, 2), "energy": round(energy, 2), "clarity": round(clarity, 2), "surprise": round(surprise, 2), "educational": round(educational, 2), "clear_argument": round(argument, 2), "controversy": round(controversy, 2), "news_relevance": round(relevance, 2), "length_fit": round(length, 2), "total": total}


def find_clip_candidates(segments: list[TranscriptSegment], *, news_keywords: set[str] | None = None, max_candidates: int = 12) -> list[dict[str, Any]]:
    units = _sentences(segments)
    cands = []
    for i in range(len(units)):
        start = units[i]["start"]
        j = i
        while j < len(units) and units[j]["end"] - start <= MAX_CLIP:
            dur = units[j]["end"] - start
            if dur >= MIN_CLIP:
                text = " ".join(u["text"] for u in units[i : j + 1])
                sc = score_window(text, dur, news_keywords=news_keywords)
                cands.append({"start": round(start, 2), "end": round(units[j]["end"], 2), "text": text, "scores": sc, "score": sc["total"]})
            j += 1
    cands.sort(key=lambda c: c["score"], reverse=True)
    chosen: list[dict[str, Any]] = []
    for c in cands:
        if all(c["end"] <= o["start"] + 3 or c["start"] >= o["end"] - 3 for o in chosen):
            chosen.append(c)
        if len(chosen) >= max_candidates:
            break
    chosen.sort(key=lambda c: c["start"])
    return chosen


SYSTEM_CLIPS = """You help pick short-form clips from the owner's own recordings. For each candidate give JSON:
{"scores": [{"index", "title" (≤60 chars, not clickbait), "caption" (≤150 chars), "why" (one sentence on why it works as a vertical clip), "platform" (youtube_short|tiktok|instagram_reel), "adjust": 0-1 (how much the candidate's boundaries feel wrong)}]}.
Only describe what is actually said; never invent quotes."""


def discover_clips(db: Session, video: Video, *, router: Router | None = None, max_candidates: int = 10, use_llm: bool = True) -> list[Clip]:
    router = router or Router(db)
    if video.transcript_status != "done":
        raise ValueError("video has no transcript yet")
    news_kw: set[str] = set()
    for s in db.execute(select(Story).where(Story.status != "ignored").order_by(Story.last_updated.desc()).limit(30)).scalars():
        news_kw.update(k for k in (s.keywords or []) if len(k) >= 4)
    cands = find_clip_candidates(video.segments, news_keywords=news_kw, max_candidates=max_candidates)
    enriched: dict[int, dict[str, Any]] = {}
    if use_llm and cands:
        user = "\n\n".join(f"[{i}] {c['start']:.1f}s–{c['end']:.1f}s\n{c['text']}" for i, c in enumerate(cands))
        try:
            data, _ = chat_json(router, "FAST", "clip_scoring", SYSTEM_CLIPS, user, max_tokens=2000)
            for row in as_list(data.get("scores")):
                if isinstance(row, dict) and "index" in row:
                    try:
                        enriched[int(row["index"])] = row
                    except (TypeError, ValueError):
                        pass
        except (ProviderError, ValueError) as e:
            log.warning("LLM clip enrichment skipped: %s", e)
    db.query(Clip).filter(Clip.video_id == video.id, Clip.status == "suggested").delete()
    clips = []
    for i, c in enumerate(cands):
        e = enriched.get(i, {})
        first_words = " ".join(c["text"].split()[:9])
        clip = Clip(
            video_id=video.id,
            start=c["start"],
            end=c["end"],
            title=as_str(e.get("title"))[:300] or first_words[:60],
            caption=as_str(e.get("caption"))[:500] or c["text"][:150],
            why_it_works=as_str(e.get("why")) or _why(c["scores"]),
            score=c["score"],
            score_breakdown=c["scores"],
            platform=as_str(e.get("platform")) if as_str(e.get("platform")) in {"youtube_short", "tiktok", "instagram_reel"} else "youtube_short",
            transcript_text=c["text"],
        )
        db.add(clip)
        clips.append(clip)
    db.commit()
    for clip in clips:
        embed_entity(db, "clip", clip, router)
    return clips


def _why(sc: dict[str, float]) -> str:
    top = sorted(((k, v) for k, v in sc.items() if k not in {"total", "length_fit"}), key=lambda kv: kv[1], reverse=True)[:2]
    return "Strong " + " and ".join(k.replace("_", " ") for k, _ in top) + f"; {sc['length_fit']:.0%} length fit."


# ---------------------------------------------------------------------------
# Rendering (9:16 with animated captions)
# ---------------------------------------------------------------------------
CAPTION_STYLES = {
    "bold_pop": {"font": "Arial", "size": 64, "primary": "&H00FFFFFF", "highlight": "&H0043F4F4", "outline": 4, "shadow": 1, "bold": -1},
    "clean": {"font": "Helvetica", "size": 56, "primary": "&H00FFFFFF", "highlight": "&H00B4AD1E", "outline": 2, "shadow": 0, "bold": 0},
    "boxed": {"font": "Arial", "size": 60, "primary": "&H00FFFFFF", "highlight": "&H0043F4F4", "outline": 0, "shadow": 0, "bold": -1, "box": True},
}


def _hex_to_ass(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "&H00FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def words_in_range(segments: list[TranscriptSegment], start: float, end: float) -> list[dict[str, float | str]]:
    words = []
    for seg in segments:
        if seg.end < start or seg.start > end:
            continue
        if seg.words:
            for w in seg.words:
                if w.get("s") is None:
                    continue
                if w["s"] >= start - 0.05 and w["e"] <= end + 0.05:
                    words.append({"w": str(w["w"]).strip(), "s": float(w["s"]) - start, "e": float(w["e"]) - start})
        else:  # no word timestamps: spread evenly
            toks = seg.text.split()
            if not toks:
                continue
            dur = (seg.end - seg.start) / len(toks)
            for i, tok in enumerate(toks):
                s = seg.start + i * dur
                if s >= start and s <= end:
                    words.append({"w": tok, "s": s - start, "e": s + dur - start})
    return [w for w in words if w["w"]]


def build_ass(words: list[dict[str, Any]], *, duration: float, width: int = 1080, height: int = 1920, style: str = "bold_pop", accent: str = "#F46543", intro_text: str = "", watermark_text: str = "", group_size: int = 4) -> str:
    st = CAPTION_STYLES.get(style, CAPTION_STYLES["bold_pop"])
    highlight = _hex_to_ass(accent) if accent else st["highlight"]
    margin_v = int(height * 0.28)  # keep captions above TikTok/Reels UI, below centre
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{st['size']},{st['primary']},&H000000FF,&H00000000,&H80000000,{st['bold']},0,0,0,100,100,0,0,{3 if st.get('box') else 1},{st['outline']},{st['shadow']},2,{int(width * 0.08)},{int(width * 0.08)},{margin_v},1
Style: Intro,{st['font']},{int(st['size'] * 1.1)},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,8,{int(width * 0.08)},{int(width * 0.08)},{int(height * 0.16)},1
Style: Mark,{st['font']},34,&H99FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,9,{int(width * 0.05)},{int(width * 0.05)},{int(height * 0.12)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if intro_text:
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(min(2.5, duration))},Intro,,0,0,0,,{{\\fad(150,250)}}{_esc(intro_text)}")
    if watermark_text:
        lines.append(f"Dialogue: 0,{_ts(0)},{_ts(duration)},Mark,,0,0,0,,{_esc(watermark_text)}")
    groups: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    for w in words:
        cur.append(w)
        if len(cur) >= group_size or re.search(r"[.!?]$", str(w["w"])):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    for g in groups:
        g_end = max(float(g[-1]["e"]), float(g[0]["s"]) + 0.3)
        for i, w in enumerate(g):
            s = float(w["s"])
            e = float(g[i + 1]["s"]) if i + 1 < len(g) else g_end
            if e <= s:
                e = s + 0.2
            parts = []
            for j, ww in enumerate(g):
                t = _esc(str(ww["w"]))
                parts.append(f"{{\\c{highlight}\\fscx108\\fscy108}}{t}{{\\r}}" if j == i else t)
            lines.append(f"Dialogue: 2,{_ts(s)},{_ts(e)},Cap,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(lines) + "\n"


def detect_face_center(video_path: str, start: float, end: float, samples: int = 5) -> float | None:
    """Average horizontal face position (0-1) using OpenCV Haar cascade, or None if unavailable."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    centers = []
    for k in range(samples):
        t = start + (end - start) * (k + 0.5) / samples
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.2, 5, minSize=(60, 60))
        if len(faces):
            x, _, w, _ = max(faces, key=lambda f: f[2] * f[3])
            centers.append((x + w / 2) / frame.shape[1])
    cap.release()
    return sum(centers) / len(centers) if centers else None


def render_clip(db: Session, clip: Clip, *, settings: dict[str, Any] | None = None, progress=None) -> Clip:
    """Cut + crop to 9:16 + burn captions. Never touches the source file."""
    cfg = get_settings()
    settings = settings or {}
    video = clip.video
    if not Path(video.path).exists():
        raise FileNotFoundError(video.path)
    media_cfg = settings_service.get(db, "media", {}) or {}
    content_cfg = settings_service.get(db, "content", {}) or {}
    out_w, out_h = (1080, 1920)
    size = settings.get("size") or media_cfg.get("default_video_size", "1080x1920")
    if "x" in str(size):
        out_w, out_h = (int(v) for v in str(size).split("x"))
    style = settings.get("caption_style") or media_cfg.get("caption_style", "bold_pop")
    accent = settings.get("accent_color") or content_cfg.get("accent_color", "#F46543")
    intro = settings.get("intro_text", "")
    progress_bar = bool(settings.get("progress_bar", False))
    watermark_text = settings.get("watermark_text", content_cfg.get("watermark_text", ""))
    watermark_path = settings.get("watermark_path", content_cfg.get("watermark_path", ""))
    captions = settings.get("captions", True)
    face_track = settings.get("face_tracking", media_cfg.get("face_tracking", True))
    pad = float(settings.get("pad", 0.0))
    start, end = max(0.0, clip.start - pad), min(video.duration or clip.end, clip.end + pad)
    duration = end - start
    if duration <= 0.5:
        raise ValueError("clip too short")
    clip.status = "rendering"
    db.commit()
    if progress:
        progress(0.05, "Preparing")
    out_dir = cfg.renders_path
    stem = re.sub(r"[^a-z0-9]+", "-", (clip.title or Path(video.filename).stem).lower()).strip("-")[:50] or "clip"
    out_path = out_dir / f"{stem}-{clip.id[:8]}.mp4"
    tmpdir = Path(tempfile.mkdtemp(prefix="poly-render-"))
    try:
        # crop geometry
        src_w, src_h = video.width or 1920, video.height or 1080
        target_ratio = out_w / out_h
        if src_w / src_h > target_ratio:
            crop_h = src_h
            crop_w = int(src_h * target_ratio) // 2 * 2
        else:
            crop_w = src_w
            crop_h = int(src_w / target_ratio) // 2 * 2
        cx = 0.5
        if face_track and crop_w < src_w:
            fc = detect_face_center(video.path, start, end)
            if fc is not None:
                cx = fc
        x = int(max(0, min(src_w - crop_w, cx * src_w - crop_w / 2)))
        y = int(max(0, (src_h - crop_h) / 2))
        filters = [f"crop={crop_w}:{crop_h}:{x}:{y}", f"scale={out_w}:{out_h}:flags=lanczos", "setsar=1"]
        if progress_bar:
            filters.append(f"drawbox=x=0:y=ih-14:w='iw*t/{duration:.3f}':h=14:color={accent.replace('#', '0x') if accent else 'white'}@0.9:t=fill")
        if captions:
            words = words_in_range(video.segments, start, end)
            ass = build_ass(words, duration=duration, width=out_w, height=out_h, style=style, accent=accent, intro_text=intro, watermark_text=watermark_text if not watermark_path else "")
            ass_path = tmpdir / "captions.ass"
            ass_path.write_text(ass, encoding="utf-8")
            ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
            filters.append(f"ass='{ass_escaped}'")
        vf = ",".join(filters)
        cmd = [_ffmpeg(), "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", video.path]
        if watermark_path and Path(watermark_path).exists():
            cmd += ["-i", watermark_path, "-filter_complex", f"[0:v]{vf}[v];[1:v]scale={int(out_w * 0.18)}:-1[wm];[v][wm]overlay=W-w-{int(out_w * 0.05)}:{int(out_h * 0.1)}[out]", "-map", "[out]", "-map", "0:a?"]
        else:
            cmd += ["-vf", vf]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_path)]
        if progress:
            progress(0.2, "Rendering with FFmpeg")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {proc.stderr[-600:]}")
        clip.render_path = str(out_path)
        clip.render_settings = {"size": f"{out_w}x{out_h}", "caption_style": style, "accent": accent, "intro_text": intro, "progress_bar": progress_bar, "watermark_text": watermark_text, "face_center": cx, "captions": captions, "start": start, "end": end}
        clip.status = "rendered"
        clip.render_error = None
        db.commit()
        return clip
    except Exception as e:
        clip.status = "failed"
        clip.render_error = str(e)[:1000]
        db.commit()
        raise
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def thumbnail(video_path: str, t: float, out_path: str, width: int = 640) -> str:
    cmd = [_ffmpeg(), "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", video_path, "-frames:v", "1", "-vf", f"scale={width}:-2", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-300:])
    return out_path


def waveform_png(video_path: str, out_path: str, width: int = 1200, height: int = 160) -> str:
    cmd = [_ffmpeg(), "-y", "-v", "error", "-i", video_path, "-filter_complex", f"showwavespic=s={width}x{height}:colors=#1EADB4", "-frames:v", "1", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-300:])
    return out_path
