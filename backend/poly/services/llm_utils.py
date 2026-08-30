"""Helpers for calling the router and parsing structured output."""
from __future__ import annotations

import json
import re
from typing import Any

from ..providers.base import ChatMessage, LLMResult
from ..providers.registry import Router

_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise ValueError("model did not return valid JSON")


def chat_json(router: Router, task: str, tag: str, system: str, user: str, *, temperature: float = 0.2, max_tokens: int | None = None, timeout: float = 300.0) -> tuple[dict[str, Any], LLMResult]:
    """Ask for JSON. `tag` is the TASK:<tag> marker used by prompts (and the mock provider)."""
    sys_msg = f"TASK:{tag}\n{system}\nRespond with a single valid JSON object only — no prose, no markdown fences."
    messages = [ChatMessage("system", sys_msg), ChatMessage("user", user)]
    res = router.chat(task, messages, temperature=temperature, max_tokens=max_tokens, json_mode=True, timeout=timeout)
    try:
        data = parse_json(res.text)
    except ValueError:
        # one repair attempt
        messages.append(ChatMessage("assistant", res.text))
        messages.append(ChatMessage("user", "That was not valid JSON. Return only the JSON object."))
        res = router.chat(task, messages, temperature=0.0, max_tokens=max_tokens, json_mode=True, timeout=timeout)
        data = parse_json(res.text)
    return data, res


def chat_text(router: Router, task: str, tag: str, system: str, user: str, *, temperature: float = 0.5, max_tokens: int | None = None, timeout: float = 300.0) -> LLMResult:
    messages = [ChatMessage("system", f"TASK:{tag}\n{system}"), ChatMessage("user", user)]
    return router.chat(task, messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)


def as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [s.strip() for s in re.split(r"\n|;", v) if s.strip()]
    return [v]


def as_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)
