"""whisper.cpp CLI transcription — fully local. Expects `whisper-cli` on PATH and a ggml model file."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

from ..base import ModelInfo, ProviderError, TranscriptionProvider, TranscriptResult, TranscriptSegmentResult, TranscriptWord


class WhisperCppProvider(TranscriptionProvider):
    name = "whisper_cpp"
    locality = "local"

    def _cli(self) -> str | None:
        return shutil.which("whisper-cli") or shutil.which("whisper-cpp")

    def available(self) -> bool:
        return self._cli() is not None

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name="ggml-base.en.bin", runtime=self.name, endpoint=self._cli() or "")]

    def transcribe(self, audio_path: str, *, model: str, language: str | None = None) -> TranscriptResult:
        cli = self._cli()
        if not cli:
            raise ProviderError("whisper.cpp CLI not found", provider=self.name, retryable=False)
        model_path = model if os.path.exists(model) else os.path.expanduser(f"~/.cache/whisper.cpp/{model}")
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "out")
            cmd = [cli, "-m", model_path, "-f", audio_path, "-oj", "-of", out]
            if language:
                cmd += ["-l", language]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise ProviderError(f"whisper.cpp failed: {proc.stderr[-500:]}", provider=self.name)
            with open(out + ".json", encoding="utf-8") as f:
                data = json.load(f)
        segments = []
        for seg in data.get("transcription", []):
            start = seg["offsets"]["from"] / 1000.0
            end = seg["offsets"]["to"] / 1000.0
            words = [
                TranscriptWord(t["text"].strip(), t["offsets"]["from"] / 1000.0, t["offsets"]["to"] / 1000.0)
                for t in seg.get("tokens", []) if t.get("text", "").strip() and not t["text"].startswith("[")
            ]
            segments.append(TranscriptSegmentResult(start, end, seg.get("text", "").strip(), words))
        return TranscriptResult(segments=segments, language=language or "en", provider=self.name, model=model)
