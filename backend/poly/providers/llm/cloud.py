"""Cloud adapters — OPTIONAL and DISABLED by default.

They are only constructed by the router when `NetworkPolicy.cloud_ai_permitted` is True, and the
policy check runs again on every call. Anthropic uses its native Messages API; OpenAI reuses the
OpenAI-compatible adapter with locality="cloud".
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from ..base import ChatMessage, LLMProvider, LLMResult, ModelInfo, ProviderError
from .openai_compat import OpenAICompatibleProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    locality = "cloud"

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def health(self) -> bool:
        return bool(self.api_key)

    def list_models(self) -> list[ModelInfo]:
        try:
            r = httpx.get(
                f"{self.base_url}/v1/models",
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                timeout=10,
            )
            r.raise_for_status()
            return [ModelInfo(name=m["id"], runtime="anthropic", endpoint=self.base_url) for m in r.json().get("data", [])]
        except httpx.HTTPError as e:
            raise ProviderError(f"Anthropic models failed: {e}", provider=self.name) from e

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
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        convo = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        if json_mode:
            system += "\n\nRespond with a single valid JSON object and nothing else."
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "messages": convo,
        }
        if system:
            payload["system"] = system
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                f"{self.base_url}/v1/messages",
                json=payload,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise ProviderError(f"Anthropic request failed: {e}", provider=self.name) from e
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
            model=model,
            provider=self.name,
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


def openai_cloud_provider(api_key: str) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "https://api.openai.com/v1", api_key=api_key, name="openai", locality="cloud", runtime="openai"
    )
