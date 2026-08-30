"""Ollama adapter (local). Uses the native Ollama HTTP API.

Endpoints used: GET /api/tags, POST /api/show, POST /api/chat, POST /api/embed, GET /api/version.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from ..base import ChatMessage, EmbeddingProvider, LLMProvider, LLMResult, ModelInfo, ProviderError


class OllamaProvider(LLMProvider, EmbeddingProvider):
    name = "ollama"
    locality = "local"

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self._probe_timeout = timeout

    # ---- discovery -------------------------------------------------------
    def health(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/version", timeout=self._probe_timeout)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def version(self) -> str:
        try:
            r = httpx.get(f"{self.base_url}/api/version", timeout=self._probe_timeout)
            return r.json().get("version", "")
        except Exception:
            return ""

    def list_models(self) -> list[ModelInfo]:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=self._probe_timeout)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama not reachable at {self.base_url}: {e}", provider=self.name) from e
        out: list[ModelInfo] = []
        for m in r.json().get("models", []):
            details = m.get("details") or {}
            name = m.get("name") or m.get("model")
            if not name:
                continue
            info = ModelInfo(
                name=name,
                runtime="ollama",
                endpoint=self.base_url,
                size_bytes=m.get("size"),
                family=details.get("family", ""),
                capabilities={
                    "parameter_size": details.get("parameter_size"),
                    "quantization": details.get("quantization_level"),
                    "families": details.get("families") or [],
                },
            )
            out.append(info)
        return out

    def show(self, model: str) -> dict[str, Any]:
        """Model card: context length, capabilities (Ollama ≥0.4 reports `capabilities`)."""
        try:
            r = httpx.post(f"{self.base_url}/api/show", json={"model": model}, timeout=self._probe_timeout * 3)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama show failed for {model}: {e}", provider=self.name) from e
        ctx = None
        for k, v in (data.get("model_info") or {}).items():
            if k.endswith(".context_length"):
                ctx = v
                break
        return {
            "context_window": ctx,
            "capabilities": data.get("capabilities") or [],
            "family": (data.get("details") or {}).get("family", ""),
            "parameters": data.get("parameters", ""),
        }

    # ---- generation ------------------------------------------------------
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        json_mode: bool = False,
        timeout: float = 180.0,
    ) -> LLMResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if json_mode:
            payload["format"] = "json"
        t0 = time.perf_counter()
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except httpx.TimeoutException as e:
            raise ProviderError(f"Ollama timed out after {timeout}s on {model}", provider=self.name) from e
        except httpx.HTTPStatusError as e:
            body = e.response.text[:300]
            retryable = e.response.status_code >= 500
            raise ProviderError(f"Ollama error {e.response.status_code}: {body}", provider=self.name, retryable=retryable) from e
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama request failed: {e}", provider=self.name) from e
        text = (data.get("message") or {}).get("content", "")
        return LLMResult(
            text=text,
            model=model,
            provider=self.name,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            latency_ms=(time.perf_counter() - t0) * 1000,
            raw={k: v for k, v in data.items() if k != "message"},
        )

    # ---- embeddings ------------------------------------------------------
    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        if not texts:
            return []
        try:
            r = httpx.post(f"{self.base_url}/api/embed", json={"model": model, "input": texts}, timeout=120)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama embed failed: {e}", provider=self.name) from e
        vecs = data.get("embeddings")
        if not vecs:
            raise ProviderError("Ollama returned no embeddings", provider=self.name)
        return [[float(x) for x in v] for v in vecs]
