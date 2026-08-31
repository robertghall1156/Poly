"""Structured-output parsing must survive what real local models actually emit.

Reasoning models (qwen3, deepseek-r1, qwq) prefix answers with <think>…</think>; smaller
models wrap JSON in prose or code fences. Poly's whole studio depends on getting the object
out regardless.
"""
from __future__ import annotations

import pytest

from poly.services.llm_utils import parse_json, strip_thinking


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"ok": true}', {"ok": True}),
        ('```json\n{"ok": true}\n```', {"ok": True}),
        ('Sure! Here is the JSON:\n{"ok": true, "n": {"deep": 2}}', {"ok": True, "n": {"deep": 2}}),
        ('{"ok": true}\nLet me know if you want changes.', {"ok": True}),
        # qwen3-style thinking, including braces inside the reasoning
        ('<think>Maybe {a: 1}? Or {x}…</think>\n{"scenes": [1], "ok": true}', {"scenes": [1], "ok": True}),
        ('<THINKING>upper case tags</THINKING>{"ok": true}', {"ok": True}),
        # truncated/unclosed thinking block with a stray brace
        ('<think>reasoning about braces {\n{"ok": true}', {"ok": True}),
        # braces inside strings must not confuse the scanner
        ('{"text": "a \\"quote\\" and { brace", "ok": true}', {"text": 'a "quote" and { brace', "ok": True}),
    ],
)
def test_parse_json_survives_real_model_output(raw, expected):
    assert parse_json(raw) == expected


def test_parse_json_prefers_the_substantive_object():
    raw = '{"note": 1}\nActually, here is the full answer:\n{"scenes": [1, 2], "title": "x", "caption": "y"}'
    assert parse_json(raw)["title"] == "x"


def test_parse_json_raises_when_there_is_no_object():
    with pytest.raises(ValueError):
        parse_json("<think>I could not do it</think> Sorry, no JSON here.")


def test_strip_thinking_leaves_prose_answers():
    assert strip_thinking("<think>x</think> plain answer") == "plain answer"
    assert strip_thinking("plain answer") == "plain answer"
