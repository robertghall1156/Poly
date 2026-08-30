"""Local generative image adapter — DISABLED until `POLY_LOCAL_IMAGE_URL` is set.

Supported kinds (POLY_LOCAL_IMAGE_KIND):
- `openai_images`: any local server exposing POST /v1/images/generations (e.g. LocalAI, some
  ComfyUI/SD-WebUI bridges). Returns b64_json.
- `a1111`: Automatic1111 / Forge — POST /sdapi/v1/txt2img.
- `comfyui`: ComfyUI — requires a workflow JSON at data/comfy_workflow.json with a
  `{{PROMPT}}` placeholder; POST /prompt then poll /history.

No model is installed automatically. See README → Local image generation for storage/hardware notes.
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx

from ...config import get_settings
from ..base import ImageProvider, ImageResult, ProviderError


class LocalGenerativeImageProvider(ImageProvider):
    name = "local_generative"
    locality = "local"

    def __init__(self, base_url: str | None = None, kind: str | None = None):
        cfg = get_settings()
        self.base_url = (base_url or cfg.local_image_url).rstrip("/")
        self.kind = kind or cfg.local_image_kind or "openai_images"

    def available(self) -> bool:
        if not self.base_url:
            return False
        try:
            r = httpx.get(self.base_url, timeout=3)
            return r.status_code < 500
        except httpx.HTTPError:
            return False

    def generate(self, prompt: str, *, out_path: str, width: int = 1024, height: int = 1024, **params) -> ImageResult:
        if not self.base_url:
            raise ProviderError("No local image model configured (POLY_LOCAL_IMAGE_URL is empty).", provider=self.name, retryable=False)
        if self.kind == "openai_images":
            data = self._openai_images(prompt, width, height, params)
        elif self.kind == "a1111":
            data = self._a1111(prompt, width, height, params)
        elif self.kind == "comfyui":
            data = self._comfyui(prompt, width, height, params)
        else:
            raise ProviderError(f"Unknown local image kind {self.kind}", provider=self.name, retryable=False)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(data)
        return ImageResult(path=out_path, width=width, height=height, provider=self.name, model=self.kind, prompt=prompt, params=params, is_generated=True)

    def _openai_images(self, prompt, width, height, params) -> bytes:
        try:
            r = httpx.post(f"{self.base_url}/v1/images/generations", json={"prompt": prompt, "size": f"{width}x{height}", "n": 1, "response_format": "b64_json", **params}, timeout=600)
            r.raise_for_status()
            return base64.b64decode(r.json()["data"][0]["b64_json"])
        except (httpx.HTTPError, KeyError) as e:
            raise ProviderError(f"local image generation failed: {e}", provider=self.name) from e

    def _a1111(self, prompt, width, height, params) -> bytes:
        try:
            r = httpx.post(f"{self.base_url}/sdapi/v1/txt2img", json={"prompt": prompt, "width": width, "height": height, "steps": params.get("steps", 25)}, timeout=600)
            r.raise_for_status()
            return base64.b64decode(r.json()["images"][0])
        except (httpx.HTTPError, KeyError) as e:
            raise ProviderError(f"A1111 generation failed: {e}", provider=self.name) from e

    def _comfyui(self, prompt, width, height, params) -> bytes:
        wf_path = get_settings().data_path / "comfy_workflow.json"
        if not wf_path.exists():
            raise ProviderError("ComfyUI workflow missing: data/comfy_workflow.json", provider=self.name, retryable=False)
        workflow = json.loads(wf_path.read_text().replace("{{PROMPT}}", prompt.replace('"', '\\"')))
        try:
            r = httpx.post(f"{self.base_url}/prompt", json={"prompt": workflow}, timeout=30)
            r.raise_for_status()
            pid = r.json()["prompt_id"]
            for _ in range(600):
                time.sleep(1)
                h = httpx.get(f"{self.base_url}/history/{pid}", timeout=10).json()
                if pid in h:
                    outputs = h[pid]["outputs"]
                    for node in outputs.values():
                        for img in node.get("images", []):
                            q = {"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")}
                            return httpx.get(f"{self.base_url}/view", params=q, timeout=30).content
            raise ProviderError("ComfyUI timed out", provider=self.name)
        except (httpx.HTTPError, KeyError) as e:
            raise ProviderError(f"ComfyUI generation failed: {e}", provider=self.name) from e
