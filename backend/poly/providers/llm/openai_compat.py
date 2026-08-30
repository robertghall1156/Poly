"""OpenAI-compatible chat/embeddings adapter.

Used for LOCAL servers (LM Studio, llama.cpp `llama-server`, vLLM, MLX `mlx_lm.server`,
LocalAI …) and, when explicitly enabled, for the OpenAI cloud API. The `locality` flag decides
which privacy rule applies; the wire format is identical.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from ..base import ChatMessage, EmbeddingProvider, LLMProvider, LLMResult, ModelInfo, ProviderError


class OpenAICompatibleProvider(LLMProvider, EmbeddingProvider):
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        name: str = "openai_compat",
        locality: str = "local",
        runtime: str = "openai_compat",
        timeout: float = 5.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.name = name
        self.locality = locality  # type: ignore[assignment]
        self.runtime = runtime
        self._probe_timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def health(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=self._probe_timeout)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[ModelInfo]:
        try:
            r = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=self._probe_timeout)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name} not reachable at {self.base_url}: {e}", provider=self.name) from e
        out = []
        for m in r.json().get("data", []):
            mid = m.get("id")
            if not mid:
                continue
            out.append(
                ModelInfo(
                    name=mid,
                    runtime=self.runtime,
                    endpoint=self.base_url,
                    context_window=m.get("max_context_length") or m.get("context_length"),
                    capabilities={"owned_by": m.get("owned_by", "")},
                )
            )
        return out

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
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        t0 = time.perf_counter()
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=self._headers(), timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except httpx.TimeoutException as e:
            raise ProviderError(f"{self.name} timed out after {timeout}s", provider=self.name) from e
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                f"{self.name} error {e.response.status_code}: {e.response.text[:300]}",
                provider=self.name,
                retryable=e.response.status_code >= 500,
            ) from e
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name} request failed: {e}", provider=self.name) from e
        choices = data.get("choices") or []
        text = (choices[0].get("message") or {}).get("content", "") if choices else ""
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
            model=model,
            provider=self.name,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        if not texts:
            return []
        try:
            r = httpx.post(
                f"{self.base_url}/embeddings", json={"model": model, "input": texts}, headers=self._headers(), timeout=120
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name} embeddings failed: {e}", provider=self.name) from e
        rows = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        return [[float(x) for x in d["embedding"]] for d in rows]
