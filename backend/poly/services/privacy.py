"""Network / privacy policy.

Three switches (persisted in the `settings` table, seeded from env):

- local_ai_only        (default ON)  — no cloud LLM / embedding / transcription / image calls
- allow_internet_research (default ON) — RSS, public websites, news & government APIs allowed
- allow_cloud_ai       (default OFF) — must be explicitly enabled; only then may a cloud AI
                                        provider be constructed, and only if local_ai_only is OFF

Every provider call passes through `NetworkPolicy.check()`.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..config import get_settings
from ..providers.base import PrivacyViolation
from . import settings as settings_service

PRIVACY_KEY = "privacy"


@dataclass
class NetworkPolicy:
    local_ai_only: bool = True
    allow_internet_research: bool = True
    allow_cloud_ai: bool = False

    @classmethod
    def load(cls, db: Session) -> "NetworkPolicy":
        cfg = get_settings()
        stored = settings_service.get(db, PRIVACY_KEY, None) or {}
        return cls(
            local_ai_only=bool(stored.get("local_ai_only", cfg.local_ai_only)),
            allow_internet_research=bool(stored.get("allow_internet_research", cfg.allow_internet_research)),
            allow_cloud_ai=bool(stored.get("allow_cloud_ai", cfg.allow_cloud_ai)),
        )

    def save(self, db: Session) -> None:
        settings_service.set(
            db,
            PRIVACY_KEY,
            {
                "local_ai_only": self.local_ai_only,
                "allow_internet_research": self.allow_internet_research,
                "allow_cloud_ai": self.allow_cloud_ai,
            },
        )

    @property
    def cloud_ai_permitted(self) -> bool:
        return self.allow_cloud_ai and not self.local_ai_only

    def check(self, *, locality: str, purpose: str, provider: str = "") -> None:
        """Raise PrivacyViolation if this call is not allowed.

        purpose: "ai" (LLM/embedding/transcription/image) or "research" (public retrieval)
        """
        if locality == "local":
            return
        if purpose == "research":
            if not self.allow_internet_research:
                raise PrivacyViolation(
                    "Internet research is disabled in Settings → Privacy & Network.", provider=provider
                )
            return
        if purpose == "ai":
            if not self.cloud_ai_permitted:
                raise PrivacyViolation(
                    "Cloud AI is disabled. Poly keeps your notes, scripts, transcripts and videos on this machine. "
                    "Enable 'Allow Cloud AI' and disable 'Local AI Only' in Settings → Privacy & Network to change this.",
                    provider=provider,
                )
            return
        raise PrivacyViolation(f"Unknown purpose {purpose!r}", provider=provider)

    def to_dict(self) -> dict:
        return {
            "local_ai_only": self.local_ai_only,
            "allow_internet_research": self.allow_internet_research,
            "allow_cloud_ai": self.allow_cloud_ai,
            "cloud_ai_permitted": self.cloud_ai_permitted,
        }
