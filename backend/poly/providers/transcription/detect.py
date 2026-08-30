"""Detect local transcription runtimes. Everything here runs on-device."""
from __future__ import annotations

import importlib.util
import platform
import shutil

from ..base import ModelInfo, TranscriptionProvider

WHISPER_SIZES = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]


def _has(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def detect_transcription_runtimes():
    from ..registry import DetectedRuntime  # local import to avoid cycle

    found = []
    if _has("mlx_whisper"):
        models = [
            ModelInfo(name=f"mlx-community/whisper-{s}-mlx", runtime="mlx_whisper", endpoint="local")
            for s in ["large-v3-turbo", "medium", "small", "base", "tiny"]
        ]
        found.append(DetectedRuntime("mlx_whisper", "local", True, "", models))
    if _has("faster_whisper"):
        models = [ModelInfo(name=s, runtime="faster_whisper", endpoint="local") for s in ["large-v3-turbo", "medium", "small", "base", "tiny"]]
        found.append(DetectedRuntime("faster_whisper", "local", True, "", models))
    cli = shutil.which("whisper-cli") or shutil.which("whisper-cpp") or shutil.which("main")
    if cli and "whisper" in cli:
        found.append(
            DetectedRuntime("whisper_cpp", cli, True, "", [ModelInfo(name="ggml-base.en.bin", runtime="whisper_cpp", endpoint=cli)])
        )
    return found


def build_transcription_provider(runtime: str) -> TranscriptionProvider:
    if runtime == "mlx_whisper":
        from .mlx_whisper import MLXWhisperProvider

        return MLXWhisperProvider()
    if runtime == "faster_whisper":
        from .faster_whisper import FasterWhisperProvider

        return FasterWhisperProvider()
    if runtime == "whisper_cpp":
        from .whisper_cpp import WhisperCppProvider

        return WhisperCppProvider()
    raise ValueError(f"unknown transcription runtime {runtime}")


def recommended_install() -> dict:
    """What to install for local transcription on this machine."""
    if is_apple_silicon():
        return {
            "runtime": "mlx_whisper",
            "command": "cd backend && uv pip install mlx-whisper",
            "why": "MLX Whisper runs on the Apple Silicon GPU/Neural Engine and is the fastest local option on this Mac.",
            "default_model": "mlx-community/whisper-large-v3-turbo",
        }
    return {
        "runtime": "faster_whisper",
        "command": "cd backend && uv pip install faster-whisper",
        "why": "faster-whisper (CTranslate2) is the fastest CPU/CUDA option.",
        "default_model": "small",
    }
