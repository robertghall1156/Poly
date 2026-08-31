"""Helpers for calling the router and parsing structured output."""
from __future__ import annotations

import json
import re
from typing import Any

from ..providers.base import ChatMessage, LLMResult
from ..providers.registry import Router

_JSON_BLOCK = re.compile(r"\{.*\}", re.S)
# Reasoning models (qwen3, deepseek-r1, qwq …) prefix their answer with a thinking block.
# It is not part of the answer and its braces would wreck JSON extraction.
_THINK_BLOCK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)
_OPEN_THINK = re.compile(r"^\s*<(think|thinking|reasoning)>.*?(?=\{|$)", re.S | re.I)


def strip_thinking(text: str) -> str:
    """Remove <think>…</think> spans so structured output survives reasoning models."""
    out = _THINK_BLOCK.sub("", text or "")
    out = _OPEN_THINK.sub("", out)  # unclosed block (truncated output)
    return out.strip()


def _balanced_objects(text: str):
    """Yield every brace-balanced {...} span, string-aware. Robust to prose, thinking text
    and stray braces around the real payload."""
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        depth, in_str, esc = 0, False, False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    yield text[i : j + 1]
                    break


def parse_json(text: str) -> dict[str, Any]:
    text = strip_thinking(text).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass
    best: dict[str, Any] | None = None
    for span in _balanced_objects(text):
        try:
            obj = json.loads(span)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and (best is None or len(span) > len(json.dumps(best))):
            best = obj
    if best is not None:
        return best
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
    res = router.chat(task, messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    res.text = strip_thinking(res.text)
    return res


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
