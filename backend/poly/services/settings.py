"""Key/value settings stored in the database (runtime-editable configuration)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import Setting

DEFAULTS: dict[str, Any] = {
    "news": {
        "topic_preferences": [],  # empty = all topics
        "max_articles_per_feed": 40,
        "relevance_threshold": 0.2,
        "lookback_days": 3,
    },
    "media": {
        "transcription_mode": "auto",  # auto | mlx_whisper | faster_whisper | whisper_cpp
        "transcription_model": "",
        "default_video_size": "1080x1920",
        "caption_style": "bold_pop",
        "face_tracking": True,
    },
    "content": {
        "default_platforms": ["youtube", "podcast", "youtube_short", "x_thread"],
        "brand_name": "",
        "watermark_text": "",
        "watermark_path": "",
        "primary_color": "#12487E",
        "accent_color": "#F46543",
    },
    "github": {"repo": "", "owner": "", "default_branch": "main"},
    "ai": {"task_overrides": {}},
    # Central brand design tokens. Renderers and the UI read these — never hard-code colors.
    "brand": {
        "primary": "#102A43",      # deep navy
        "accent": "#0F766E",       # teal
        "secondary": "#52667A",    # slate
        "background": "#F8F9FA",   # warm off-white
        "highlight": "#C89B3C",    # muted gold
        "text_on_dark": "#F8F9FA",
        "text_on_light": "#102A43",
        "font": "",                 # empty = system font stack (Arial/Helvetica on macOS)
        "logo_text": "",            # small corner mark on videos/carousels; empty = none
    },
    "voice": {
        "mode": "none",            # none | tts   ("my voice later" is a future provider slot)
        "engine": "auto",          # auto | say | piper
        "voice": "",               # engine-specific voice name (e.g. macOS "Samantha")
        "rate": 180,                # words per minute for say
        "piper_model": "",         # path to a piper .onnx voice, if using piper
    },
}


def get(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key, default) if default is None else default
    return row.value


def set(db: Session, key: str, value: Any) -> Any:  # noqa: A001 - mirrors dict API
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    return value


def update(db: Session, key: str, patch: dict[str, Any]) -> Any:
    current = dict(get(db, key, {}) or {})
    current.update(patch)
    return set(db, key, current)


def all_settings(db: Session) -> dict[str, Any]:
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in DEFAULTS.items()}
    for row in db.query(Setting).all():
        if isinstance(row.value, dict) and isinstance(out.get(row.key), dict):
            merged = dict(out[row.key])
            merged.update(row.value)
            out[row.key] = merged
        else:
            out[row.key] = row.value
    return out
