"""faster-whisper (CTranslate2) transcription — fully local."""
from __future__ import annotations

import importlib.util

from ..base import (
    ModelInfo,
    ProviderError,
    TranscriptionProvider,
    TranscriptResult,
    TranscriptSegmentResult,
    TranscriptWord,
)


class FasterWhisperProvider(TranscriptionProvider):
    name = "faster_whisper"
    locality = "local"
    _models: dict[str, object] = {}

    def available(self) -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name=s, runtime=self.name, endpoint="local") for s in ["large-v3-turbo", "medium", "small", "base", "tiny"]]

    def transcribe(self, audio_path: str, *, model: str, language: str | None = None) -> TranscriptResult:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ProviderError("faster-whisper is not installed (uv pip install faster-whisper)", provider=self.name, retryable=False) from e
        try:
            wm = self._models.get(model)
            if wm is None:
                wm = WhisperModel(model, device="auto", compute_type="auto")
                self._models[model] = wm
            segs, info = wm.transcribe(audio_path, word_timestamps=True, language=language, vad_filter=True)  # type: ignore[attr-defined]
            segments = []
            for seg in segs:
                words = [TranscriptWord(w.word.strip(), float(w.start), float(w.end)) for w in (seg.words or [])]
                segments.append(TranscriptSegmentResult(float(seg.start), float(seg.end), seg.text.strip(), words))
        except Exception as e:
            raise ProviderError(f"faster-whisper failed: {e}", provider=self.name) from e
        return TranscriptResult(segments=segments, language=getattr(info, "language", language or "en"), provider=self.name, model=model)
