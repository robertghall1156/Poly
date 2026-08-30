"""Provider interfaces.

Nothing outside `poly.providers` may import a concrete runtime (Ollama, LM Studio, Whisper …).
Services ask the registry/router for a provider by *task* and call these interfaces only.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Locality = Literal["local", "cloud"]


class ProviderError(Exception):
    """A provider failed. `retryable` tells the job system whether to keep the task."""

    def __init__(self, message: str, *, provider: str = "", retryable: bool = True):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


class PrivacyViolation(ProviderError):
    """Raised when a call would leave the machine and policy forbids it."""

    def __init__(self, message: str, *, provider: str = ""):
        super().__init__(message, provider=provider, retryable=False)


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelInfo:
    name: str
    runtime: str
    endpoint: str
    size_bytes: int | None = None
    context_window: int | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    family: str = ""


class LLMProvider(abc.ABC):
    """Chat-completion style text generation."""

    name: str = "llm"
    locality: Locality = "local"

    @abc.abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        json_mode: bool = False,
        timeout: float = 180.0,
    ) -> LLMResult: ...

    @abc.abstractmethod
    def list_models(self) -> list[ModelInfo]: ...

    @abc.abstractmethod
    def health(self) -> bool: ...


class EmbeddingProvider(abc.ABC):
    name: str = "embedding"
    locality: Locality = "local"
    dimension: int = 768

    @abc.abstractmethod
    def embed(self, texts: list[str], *, model: str) -> list[list[float]]: ...

    @abc.abstractmethod
    def health(self) -> bool: ...


@dataclass
class TranscriptWord:
    word: str
    start: float
    end: float


@dataclass
class TranscriptSegmentResult:
    start: float
    end: float
    text: str
    words: list[TranscriptWord] = field(default_factory=list)


@dataclass
class TranscriptResult:
    segments: list[TranscriptSegmentResult]
    language: str
    provider: str
    model: str


class TranscriptionProvider(abc.ABC):
    name: str = "transcription"
    locality: Locality = "local"

    @abc.abstractmethod
    def transcribe(self, audio_path: str, *, model: str, language: str | None = None) -> TranscriptResult: ...

    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def list_models(self) -> list[ModelInfo]: ...


@dataclass
class ImageResult:
    path: str
    width: int
    height: int
    provider: str
    model: str
    prompt: str
    params: dict[str, Any] = field(default_factory=dict)
    is_generated: bool = False


class ImageProvider(abc.ABC):
    name: str = "image"
    locality: Locality = "local"

    @abc.abstractmethod
    def generate(self, prompt: str, *, out_path: str, width: int = 1024, height: int = 1024, **params) -> ImageResult: ...

    @abc.abstractmethod
    def available(self) -> bool: ...


@dataclass
class RawArticle:
    """What a news provider returns before normalisation."""

    url: str
    title: str
    publication: str = ""
    author: str | None = None
    published_at: datetime | None = None
    summary: str = ""
    content: str = ""
    provider: str = "rss"
    feed_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class NewsProvider(abc.ABC):
    """Public-internet retrieval. Receives only the query/feed URL — never private context."""

    name: str = "news"
    locality: Locality = "cloud"  # it is network retrieval; gated by allow_internet_research
    requires_key: bool = False

    @abc.abstractmethod
    def fetch(self, feed_url: str | None = None, query: str | None = None, *, limit: int = 50) -> list[RawArticle]: ...

    @abc.abstractmethod
    def available(self) -> bool: ...
