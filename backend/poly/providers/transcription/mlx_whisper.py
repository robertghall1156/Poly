"""MLX Whisper (Apple Silicon) transcription — fully local."""
from __future__ import annotations

import importlib.util

from ..base import ModelInfo, ProviderError, TranscriptionProvider, TranscriptResult, TranscriptSegmentResult, TranscriptWord


class MLXWhisperProvider(TranscriptionProvider):
    name = "mlx_whisper"
    locality = "local"

    def available(self) -> bool:
        return importlib.util.find_spec("mlx_whisper") is not None

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name=f"mlx-community/whisper-{s}-mlx", runtime=self.name, endpoint="local") for s in ["large-v3-turbo", "medium", "small", "base"]]

    def transcribe(self, audio_path: str, *, model: str, language: str | None = None) -> TranscriptResult:
        try:
            import mlx_whisper  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ProviderError("mlx-whisper is not installed (uv pip install mlx-whisper)", provider=self.name, retryable=False) from e
        try:
            result = mlx_whisper.transcribe(audio_path, path_or_hf_repo=model, word_timestamps=True, language=language)
        except Exception as e:
            raise ProviderError(f"mlx-whisper failed: {e}", provider=self.name) from e
        segments = []
        for seg in result.get("segments", []):
            words = [TranscriptWord(w.get("word", "").strip(), float(w["start"]), float(w["end"])) for w in seg.get("words", []) if "start" in w]
            segments.append(TranscriptSegmentResult(float(seg["start"]), float(seg["end"]), seg.get("text", "").strip(), words))
        return TranscriptResult(segments=segments, language=result.get("language", language or "en"), provider=self.name, model=model)
