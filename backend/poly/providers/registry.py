"""Local model registry, runtime detection and task routing.

- `detect_and_register(db)` scans supported local runtimes, enumerates models, records them in
  `local_models`, and recommends task assignments. It never modifies the runtimes themselves.
- `Router` picks the best enabled model for a task category and falls back to the next *local*
  model on failure. It never silently falls back to a cloud provider.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import TASK_CATEGORIES, LocalModel
from ..services.privacy import NetworkPolicy
from .base import (
    ChatMessage,
    EmbeddingProvider,
    LLMProvider,
    LLMResult,
    ModelInfo,
    PrivacyViolation,
    ProviderError,
    TranscriptionProvider,
)
from .embeddings.hashing import MODEL_NAME as HASHING_MODEL
from .embeddings.hashing import HashingEmbeddingProvider
from .llm.mock import MockLLMProvider
from .llm.ollama import OllamaProvider
from .llm.openai_compat import OpenAICompatibleProvider

log = logging.getLogger(__name__)

CHAT_RUNTIMES = {"ollama", "openai_compat", "lmstudio", "llamacpp", "vllm", "mlx", "mock", "anthropic", "openai"}
TRANSCRIPTION_RUNTIMES = {"mlx_whisper", "faster_whisper", "whisper_cpp"}

_EMBED_PAT = re.compile(r"embed|bge|e5-|minilm|gte-|arctic-embed|nomic", re.I)
_VISION_PAT = re.compile(r"llava|vision|-vl|moondream|minicpm-v|bakllava|pixtral|gemma3|qwen.*vl", re.I)
_REASON_PAT = re.compile(r"r1|reason|think|qwq|o1|o3|deepseek|phi-4|gpt-oss", re.I)
_PARAM_PAT = re.compile(r"(\d+(?:\.\d+)?)\s*[bB]\b")


def _param_billions(info: ModelInfo) -> float | None:
    p = (info.capabilities or {}).get("parameter_size")
    if p:
        m = _PARAM_PAT.search(str(p))
        if m:
            return float(m.group(1))
    m = _PARAM_PAT.search(info.name)
    if m:
        return float(m.group(1))
    if info.size_bytes:
        return round(info.size_bytes / 6e8, 1)  # rough q4 estimate
    return None


def classify_tasks(info: ModelInfo) -> list[str]:
    """Guess which task categories a model is suitable for from its name/metadata."""
    name = info.name.lower()
    caps = (info.capabilities or {}).get("capabilities") or []
    if _EMBED_PAT.search(name) or "embedding" in caps:
        return ["EMBEDDING"]
    tasks: list[str] = []
    if _VISION_PAT.search(name) or "vision" in caps:
        tasks.append("VISION")
    b = _param_billions(info)
    if b is None:
        tasks += ["FAST", "WRITING", "REASONING"]
    elif b <= 5:
        tasks += ["FAST", "WRITING"]
    elif b <= 12:
        tasks += ["FAST", "WRITING", "REASONING"]
    else:
        tasks += ["REASONING", "WRITING"]
    if _REASON_PAT.search(name) and "REASONING" not in tasks:
        tasks.append("REASONING")
    return tasks


def task_score(row: LocalModel, task: str) -> int:
    """Secondary ordering within the same user priority. Lower = tried first.
    Prefer small models for FAST, large (and reasoning-tuned) models for REASONING/WRITING."""
    info = ModelInfo(name=row.name, runtime=row.runtime, endpoint=row.endpoint, size_bytes=row.size_bytes, capabilities=row.capabilities or {})
    return _priority_for(info, task)


def _priority_for(info: ModelInfo, task: str) -> int:
    """Lower = tried first. Prefer small models for FAST, large for REASONING/WRITING."""
    b = _param_billions(info) or 7.0
    if task == "FAST":
        return int(abs(b - 4) * 10)
    if task == "REASONING":
        bonus = -50 if _REASON_PAT.search(info.name) else 0
        return int(max(0, 100 - b)) + bonus
    if task == "WRITING":
        return int(max(0, 100 - b))
    return 100


@dataclass
class DetectedRuntime:
    runtime: str
    endpoint: str
    running: bool
    version: str = ""
    models: list[ModelInfo] | None = None
    error: str = ""


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def scan_runtimes() -> list[DetectedRuntime]:
    cfg = get_settings()
    found: list[DetectedRuntime] = []

    ollama = OllamaProvider(cfg.ollama_url)
    if ollama.health():
        try:
            models = ollama.list_models()
            for m in models:
                try:
                    card = ollama.show(m.name)
                    m.context_window = card.get("context_window")
                    m.capabilities["capabilities"] = card.get("capabilities", [])
                except ProviderError:
                    pass
            found.append(DetectedRuntime("ollama", cfg.ollama_url, True, ollama.version(), models))
        except ProviderError as e:
            found.append(DetectedRuntime("ollama", cfg.ollama_url, True, "", [], str(e)))
    else:
        found.append(DetectedRuntime("ollama", cfg.ollama_url, False))

    for url in cfg.openai_compat_url_list:
        runtime = "lmstudio" if ":1234" in url else "openai_compat"
        prov = OpenAICompatibleProvider(url, runtime=runtime, name=runtime)
        if prov.health():
            try:
                found.append(DetectedRuntime(runtime, url, True, "", prov.list_models()))
            except ProviderError as e:
                found.append(DetectedRuntime(runtime, url, True, "", [], str(e)))
        else:
            found.append(DetectedRuntime(runtime, url, False))

    found.extend(scan_transcription())
    return found


def scan_transcription() -> list[DetectedRuntime]:
    from .transcription.detect import detect_transcription_runtimes

    return detect_transcription_runtimes()


def detect_and_register(db: Session) -> dict[str, Any]:
    """Scan runtimes and upsert `local_models`. Returns a summary for the UI."""
    runtimes = scan_runtimes()
    seen: set[tuple[str, str, str]] = set()
    added = 0
    for rt in runtimes:
        for m in rt.models or []:
            key = (m.name, rt.runtime, rt.endpoint)
            seen.add(key)
            row = db.execute(
                select(LocalModel).where(
                    LocalModel.name == m.name, LocalModel.runtime == rt.runtime, LocalModel.endpoint == rt.endpoint
                )
            ).scalar_one_or_none()
            tasks = ["TRANSCRIPTION"] if rt.runtime in TRANSCRIPTION_RUNTIMES else classify_tasks(m)
            if row is None:
                row = LocalModel(
                    name=m.name,
                    runtime=rt.runtime,
                    endpoint=rt.endpoint,
                    tasks=tasks,
                    priority=100,  # user-adjustable; per-task ordering comes from task_score()
                    enabled=True,
                )
                db.add(row)
                added += 1
            row.detected = True
            row.size_bytes = m.size_bytes
            row.context_window = m.context_window or row.context_window
            row.capabilities = {**(row.capabilities or {}), **(m.capabilities or {}), "family": m.family}
            if not row.tasks:
                row.tasks = tasks
    # mark models that disappeared
    for row in db.execute(select(LocalModel).where(LocalModel.locality == "local")).scalars():
        if (row.name, row.runtime, row.endpoint) not in seen and row.runtime != "mock":
            row.detected = False

    if os.environ.get("POLY_MOCK_LLM") == "1":
        _ensure_mock(db)
    db.commit()
    return {
        "runtimes": [
            {"runtime": r.runtime, "endpoint": r.endpoint, "running": r.running, "version": r.version,
             "model_count": len(r.models or []), "error": r.error}
            for r in runtimes
        ],
        "models_added": added,
        "assignments": recommend_assignments(db),
    }


def _ensure_mock(db: Session) -> None:
    row = db.execute(select(LocalModel).where(LocalModel.runtime == "mock")).scalar_one_or_none()
    if row is None:
        db.add(
            LocalModel(
                name="mock-model", runtime="mock", endpoint="mock://", tasks=["FAST", "REASONING", "WRITING", "EMBEDDING"],
                priority=1000, enabled=True, detected=True, context_window=8192,
            )
        )


def recommend_assignments(db: Session) -> dict[str, str | None]:
    """Best model per task category (name) — what the router would pick right now."""
    out: dict[str, str | None] = {}
    for task in TASK_CATEGORIES:
        c = candidates(db, task)
        out[task] = f"{c[0].runtime}:{c[0].name}" if c else None
    if out.get("EMBEDDING") is None:
        out["EMBEDDING"] = f"hashing:{HASHING_MODEL} (fallback — pull an embedding model for semantic search)"
    return out


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
TASK_FALLBACKS = {"FAST": ["WRITING", "REASONING"], "WRITING": ["REASONING", "FAST"], "REASONING": ["WRITING", "FAST"]}


def candidates(db: Session, task: str, *, include_cloud: bool = False) -> list[LocalModel]:
    """Enabled, detected models assigned to `task`, best first. If nothing is assigned to a chat
    task, neighbouring chat categories are used so a single installed model still serves everything."""
    rows = db.execute(
        select(LocalModel).where(LocalModel.enabled.is_(True), LocalModel.detected.is_(True))
    ).scalars().all()
    rows = [r for r in rows if include_cloud or r.locality == "local"]
    primary = [r for r in rows if task in (r.tasks or [])]
    primary.sort(key=lambda r: (r.priority, task_score(r, task), -(r.size_bytes or 0)))
    if primary:
        return primary
    for alt in TASK_FALLBACKS.get(task, []):
        alt_rows = [r for r in rows if alt in (r.tasks or [])]
        if alt_rows:
            alt_rows.sort(key=lambda r: (r.priority, task_score(r, task), -(r.size_bytes or 0)))
            return alt_rows
    return []


def build_provider(row: LocalModel) -> LLMProvider | EmbeddingProvider | TranscriptionProvider:
    cfg = get_settings()
    if row.runtime == "ollama":
        return OllamaProvider(row.endpoint or cfg.ollama_url)
    if row.runtime in {"openai_compat", "lmstudio", "llamacpp", "vllm", "mlx"}:
        return OpenAICompatibleProvider(row.endpoint, runtime=row.runtime, name=row.runtime)
    if row.runtime == "mock":
        return MockLLMProvider()
    if row.runtime == "anthropic":
        from .llm.cloud import AnthropicProvider

        return AnthropicProvider(cfg.anthropic_api_key)
    if row.runtime == "openai":
        from .llm.cloud import openai_cloud_provider

        return openai_cloud_provider(cfg.openai_api_key)
    if row.runtime in TRANSCRIPTION_RUNTIMES:
        from .transcription.detect import build_transcription_provider

        return build_transcription_provider(row.runtime)
    raise ProviderError(f"Unknown runtime {row.runtime}", provider=row.runtime, retryable=False)


class NoModelAvailable(ProviderError):
    def __init__(self, task: str, failures: list[str]):
        msg = f"No local model could complete task {task}."
        if failures:
            msg += " Tried: " + "; ".join(failures)
        else:
            msg += " No enabled local model is assigned to this task (Settings → Local AI)."
        super().__init__(msg, provider="router", retryable=True)
        self.task = task
        self.failures = failures


class Router:
    """Selects a model for a task and handles local fallback."""

    def __init__(self, db: Session, policy: NetworkPolicy | None = None):
        self.db = db
        self.policy = policy or NetworkPolicy.load(db)
        self._mock = os.environ.get("POLY_MOCK_LLM") == "1"

    def _record(self, row: LocalModel, ok: bool, latency_ms: float | None = None, error: str | None = None) -> None:
        if ok:
            row.last_ok_at = _now()
            row.last_latency_ms = latency_ms
            row.last_error = None
        else:
            row.last_error = (error or "")[:1000]
        try:
            self.db.commit()
        except Exception:  # pragma: no cover
            self.db.rollback()

    def chat(
        self,
        task: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        json_mode: bool = False,
        timeout: float = 240.0,
        allow_cloud: bool = False,
        preferred_model: str | None = None,
    ) -> LLMResult:
        rows = candidates(self.db, task, include_cloud=allow_cloud and self.policy.cloud_ai_permitted)
        if preferred_model:
            rows.sort(key=lambda r: 0 if r.name == preferred_model else 1)
        failures: list[str] = []
        for row in rows:
            try:
                self.policy.check(locality=row.locality, purpose="ai", provider=row.runtime)
            except PrivacyViolation as e:
                failures.append(f"{row.runtime}:{row.name} blocked ({e})")
                continue
            try:
                provider = build_provider(row)
                assert isinstance(provider, LLMProvider)
                res = provider.chat(
                    messages, model=row.name, temperature=temperature, max_tokens=max_tokens,
                    json_mode=json_mode, timeout=timeout,
                )
                self._record(row, True, res.latency_ms)
                res.raw["locality"] = row.locality
                return res
            except ProviderError as e:
                log.warning("model %s:%s failed for %s: %s", row.runtime, row.name, task, e)
                self._record(row, False, error=str(e))
                failures.append(f"{row.runtime}:{row.name} → {e}")
                continue
        raise NoModelAvailable(task, failures)

    def embedding_model(self) -> tuple[EmbeddingProvider, str]:
        rows = candidates(self.db, "EMBEDDING")
        for row in rows:
            try:
                provider = build_provider(row)
                if isinstance(provider, EmbeddingProvider):
                    return provider, row.name
            except ProviderError:
                continue
        return HashingEmbeddingProvider(), HASHING_MODEL

    def embed(self, texts: list[str]) -> tuple[list[list[float]], str]:
        rows = candidates(self.db, "EMBEDDING")
        failures = []
        for row in rows:
            try:
                provider = build_provider(row)
                assert isinstance(provider, EmbeddingProvider)
                t0 = time.perf_counter()
                vecs = provider.embed(texts, model=row.name)
                self._record(row, True, (time.perf_counter() - t0) * 1000)
                return vecs, row.name
            except ProviderError as e:
                self._record(row, False, error=str(e))
                failures.append(str(e))
        return HashingEmbeddingProvider().embed(texts), HASHING_MODEL

    def transcription(self, preferred_runtime: str | None = None) -> tuple[TranscriptionProvider, str] | None:
        rows = candidates(self.db, "TRANSCRIPTION")
        if preferred_runtime and preferred_runtime != "auto":
            rows = [r for r in rows if r.runtime == preferred_runtime] + [r for r in rows if r.runtime != preferred_runtime]
        for row in rows:
            try:
                provider = build_provider(row)
                if isinstance(provider, TranscriptionProvider) and provider.available():
                    return provider, row.name
            except ProviderError:
                continue
        return None


def test_model(db: Session, model_id: str) -> dict[str, Any]:
    """Health + latency probe for one registered model."""
    row = db.get(LocalModel, model_id)
    if row is None:
        raise ProviderError("model not found", retryable=False)
    provider = build_provider(row)
    t0 = time.perf_counter()
    try:
        if "EMBEDDING" in (row.tasks or []) and isinstance(provider, EmbeddingProvider) and not isinstance(provider, MockLLMProvider):
            vec = provider.embed(["Poly health check"], model=row.name)
            detail = f"{len(vec[0])}-d embedding"
        elif isinstance(provider, TranscriptionProvider):
            ok = provider.available()
            detail = "available" if ok else "not available"
            if not ok:
                raise ProviderError("transcription runtime not available", provider=row.runtime)
        else:
            assert isinstance(provider, LLMProvider)
            res = provider.chat([ChatMessage("user", "Reply with the single word: ready")], model=row.name, max_tokens=8, timeout=120)
            detail = res.text.strip()[:80]
        ms = (time.perf_counter() - t0) * 1000
        row.last_ok_at = _now()
        row.last_latency_ms = ms
        row.last_error = None
        db.commit()
        return {"ok": True, "latency_ms": round(ms, 1), "detail": detail}
    except ProviderError as e:
        row.last_error = str(e)
        db.commit()
        return {"ok": False, "latency_ms": None, "detail": str(e)}


def ffmpeg_available() -> dict[str, Any]:
    cfg = get_settings()
    path = shutil.which(cfg.ffmpeg_path)
    probe = shutil.which(cfg.ffprobe_path)
    return {"ffmpeg": path, "ffprobe": probe, "ok": bool(path and probe)}
