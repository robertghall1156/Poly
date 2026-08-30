"""Local text-to-speech providers. Everything runs on-device.

- SayProvider: macOS built-in `say` (no install, decent quality voices).
- PiperProvider: piper CLI + a local .onnx voice model, if installed.
- SilenceProvider: produces a silent track sized to the narration (used when no engine is
  available and in tests) — the video still renders, just without voice.

"My voice later": a future `UserVoiceProvider` slots in here behind the same interface, and must
only ever use a voice profile the owner recorded and authorised. Cloning or imitating another real
person's voice is out of scope and prohibited.
"""
from __future__ import annotations

import abc
import shutil
import subprocess
from pathlib import Path

from ..base import ProviderError

WORDS_PER_SECOND = 2.6  # conservative spoken pace, used for estimates and silence sizing


def estimate_seconds(text: str) -> float:
    return max(0.8, len(text.split()) / WORDS_PER_SECOND)


class TTSProvider(abc.ABC):
    name = "tts"
    locality = "local"

    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def synthesize(self, text: str, out_wav: str, *, voice: str = "", rate: int = 180) -> float:
        """Write a 16-bit WAV; return its duration in seconds."""


def _wav_duration(path: str) -> float:
    import wave

    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def _ffmpeg_convert(src: str, out_wav: str) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", src, "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", out_wav],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise ProviderError(f"audio convert failed: {proc.stderr[-300:]}", provider="tts")


class SayProvider(TTSProvider):
    name = "say"

    def available(self) -> bool:
        return shutil.which("say") is not None

    def synthesize(self, text: str, out_wav: str, *, voice: str = "", rate: int = 180) -> float:
        aiff = out_wav + ".aiff"
        cmd = ["say", "-o", aiff, "-r", str(rate)]
        if voice:
            cmd += ["-v", voice]
        cmd.append(text)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise ProviderError(f"say failed: {proc.stderr[-300:]}", provider=self.name)
        _ffmpeg_convert(aiff, out_wav)
        Path(aiff).unlink(missing_ok=True)
        return _wav_duration(out_wav)


class PiperProvider(TTSProvider):
    name = "piper"

    def __init__(self, model_path: str = ""):
        self.model_path = model_path

    def available(self) -> bool:
        return shutil.which("piper") is not None and bool(self.model_path) and Path(self.model_path).exists()

    def synthesize(self, text: str, out_wav: str, *, voice: str = "", rate: int = 180) -> float:
        proc = subprocess.run(
            ["piper", "--model", self.model_path, "--output_file", out_wav],
            input=text, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise ProviderError(f"piper failed: {proc.stderr[-300:]}", provider=self.name)
        return _wav_duration(out_wav)


class SilenceProvider(TTSProvider):
    name = "silence"

    def available(self) -> bool:
        return True

    def synthesize(self, text: str, out_wav: str, *, voice: str = "", rate: int = 180) -> float:
        dur = estimate_seconds(text)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{dur:.2f}", "-c:a", "pcm_s16le", out_wav],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise ProviderError(f"silence synth failed: {proc.stderr[-300:]}", provider=self.name)
        return dur


def pick_tts(engine: str = "auto", piper_model: str = "") -> TTSProvider:
    if engine == "say":
        return SayProvider()
    if engine == "piper":
        return PiperProvider(piper_model)
    if engine == "auto":
        say = SayProvider()
        if say.available():
            return say
        piper = PiperProvider(piper_model)
        if piper.available():
            return piper
    return SilenceProvider()


def tts_status(piper_model: str = "") -> dict:
    return {
        "say": SayProvider().available(),
        "piper": PiperProvider(piper_model).available(),
        "active": pick_tts("auto", piper_model).name,
    }
