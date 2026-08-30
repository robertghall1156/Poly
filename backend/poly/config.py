"""Application configuration.

Everything comes from environment variables (or a `.env` file in the repo root / backend dir).
Runtime-editable settings (privacy switches, feeds, folders, branding) live in the `settings`
table and are managed by `services.settings`; this module only covers process-level config.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


def _find_env_file() -> str | None:
    for candidate in (REPO_DIR / ".env", BACKEND_DIR / ".env"):
        if candidate.exists():
            return str(candidate)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_find_env_file(), env_prefix="POLY_", extra="ignore")

    database_url: str = "sqlite:///./data/poly.db"
    data_dir: str = "./data"
    knowledge_file: str = "./knowledge/political_operating_system.md"
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    ollama_url: str = "http://localhost:11434"
    openai_compat_urls: str = "http://localhost:1234/v1"

    local_ai_only: bool = True
    allow_internet_research: bool = True
    allow_cloud_ai: bool = False

    local_image_url: str = ""
    local_image_kind: str = ""

    host: str = "127.0.0.1"
    port: int = 8000
    daily_ingest_hour: int = 6
    daily_ingest_minute: int = 30

    # Not prefixed with POLY_ — read directly from the environment.
    @property
    def anthropic_api_key(self) -> str:
        return os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def openai_api_key(self) -> str:
        return os.environ.get("OPENAI_API_KEY", "")

    @property
    def brave_api_key(self) -> str:
        return os.environ.get("BRAVE_API_KEY", "")

    @property
    def tavily_api_key(self) -> str:
        return os.environ.get("TAVILY_API_KEY", "")

    @property
    def newsapi_key(self) -> str:
        return os.environ.get("NEWSAPI_KEY", "")

    # ---- resolved paths -------------------------------------------------
    def _resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (REPO_DIR / path).resolve()

    @property
    def data_path(self) -> Path:
        path = self._resolve(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def renders_path(self) -> Path:
        p = self.data_path / "renders"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def images_path(self) -> Path:
        p = self.data_path / "images"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cache_path(self) -> Path:
        p = self.data_path / "cache"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def knowledge_path(self) -> Path:
        return self._resolve(self.knowledge_file)

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:///./"):
            rel = url[len("sqlite:///./"):]
            full = (REPO_DIR / rel).resolve()
            full.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{full}"
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def openai_compat_url_list(self) -> list[str]:
        return [u.strip() for u in self.openai_compat_urls.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
