"""Deterministic mock LLM for tests and for `POLY_MOCK_LLM=1` development.

It is a DEVELOPMENT FIXTURE, never used in normal operation. It returns structured JSON that
satisfies each service's schema so end-to-end flows can be exercised without a model.
"""
from __future__ import annotations

import json
import re

from ..base import ChatMessage, EmbeddingProvider, LLMProvider, LLMResult, ModelInfo


class MockLLMProvider(LLMProvider, EmbeddingProvider):
    name = "mock"
    locality = "local"

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[list[ChatMessage]] = []

    def health(self) -> bool:
        return not self.fail

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name="mock-model", runtime="mock", endpoint="mock://")]

    def chat(self, messages, *, model, temperature=0.4, max_tokens=None, json_mode=False, timeout=180.0) -> LLMResult:
        from ..base import ProviderError

        if self.fail:
            raise ProviderError("mock failure", provider=self.name)
        self.calls.append(messages)
        last = messages[-1].content if messages else ""
        sys = " ".join(m.content for m in messages if m.role == "system")
        kind = re.search(r"TASK:(\w+)", sys + last)
        task = kind.group(1) if kind else "generic"
        if json_mode:
            return LLMResult(text=json.dumps(self._json_for(task, last)), model=model, provider=self.name)
        return LLMResult(text=f"[mock {task}] " + last[:200], model=model, provider=self.name)

    def _json_for(self, task: str, prompt: str) -> dict:
        if task == "story_analysis":
            return {
                "summary": "Mock summary of the story.",
                "why_it_matters": "It touches taxation and corporate power.",
                "topics": ["taxes", "corporate power"],
                "claims": [
                    {"text": "The bill raises the corporate rate to 25%.", "claim_type": "FACT", "supporting_passage": "raises the corporate rate"},
                    {"text": "Critics say it will slow hiring.", "claim_type": "OPINION", "supporting_passage": ""},
                ],
                "arguments": [
                    {"side": "for", "argument": "Closes loopholes."},
                    {"side": "against", "argument": "May reduce investment."},
                ],
                "unresolved_questions": ["What is the revenue estimate?"],
                "competing_interpretations": ["Fairness measure vs. anti-growth measure"],
                "content_potential": [{"format": "youtube", "angle": "How corporate tax avoidance actually works", "score": 0.8}],
                "recommended_format": "youtube",
                "principle_links": [],
            }
        if task == "think_question":
            return {"question": "What is your initial instinct on this, and which of your principles does it rest on?", "kind": "instinct"}
        if task == "position_brief":
            return {
                "issue": "Mock issue",
                "position": "Mock position",
                "rationale": "Mock rationale",
                "governing_principle": "Power needs counterweights",
                "strongest_for": "For",
                "strongest_against": "Against",
                "response": "Response",
                "factual_assumptions": ["Assumption A"],
                "unresolved_questions": ["Question B"],
                "policy_mechanisms": ["Mechanism C"],
                "confidence": 0.6,
            }
        if task == "longform":
            return {
                "working_title": "Why the system works this way",
                "alternative_titles": ["Alt 1", "Alt 2", "Alt 3"],
                "hook": "Hook",
                "opening_30s": "Opening",
                "thesis": "Thesis",
                "outline": [{"section": s, "notes": f"Notes for {s}"} for s in [
                    "QUESTION", "WHY PEOPLE CARE", "HOW THE CURRENT SYSTEM WORKS", "HOW WE GOT HERE", "WHAT IS WORKING",
                    "WHAT IS BROKEN", "STRONGEST COUNTERARGUMENT", "MY VIEW", "WHAT I WOULD CHANGE", "WHAT COULD GO WRONG", "CONCLUSION"]],
                "research_needed": ["R1"],
                "arguments": ["A1"],
                "counterarguments": ["C1"],
                "examples": ["E1"],
                "evidence": ["Ev1"],
                "transitions": ["T1"],
                "conclusion": "Conclusion",
                "call_to_discussion": "What would you change?",
                "show_notes": "Show notes",
                "sources": ["https://example.gov/report"],
            }
        if task == "social":
            return {
                "posts": ["Post 1", "Post 2", "Post 3"],
                "thread": ["1/ Thread start", "2/ Middle", "3/ End"],
                "quote_cards": ["Quote A", "Quote B"],
                "short_video_ideas": ["Idea 1", "Idea 2"],
                "hooks": ["H1", "H2", "H3", "H4", "H5"],
                "titles": ["T1", "T2", "T3", "T4", "T5"],
                "thumbnail_text": ["Thumb 1", "Thumb 2"],
                "meme_concepts": ["M1", "M2", "M3"],
            }
        if task == "factcheck":
            return {
                "claims": [
                    {"text": "The corporate rate is 21%.", "status": "VERIFIED", "sources": ["https://www.irs.gov"], "notes": ""},
                    {"text": "Most billionaires pay nothing.", "status": "UNVERIFIED", "sources": [], "notes": "needs data"},
                ]
            }
        if task == "clip_scoring":
            return {"scores": [{"index": 0, "hook": 0.8, "self_contained": 0.7, "energy": 0.6, "clarity": 0.8, "surprise": 0.5, "educational": 0.8, "controversy": 0.3, "news_relevance": 0.4, "title": "Mock clip", "caption": "Mock caption", "why": "Strong hook"}]}
        if task == "video_summary":
            return {"summary": "Mock video summary", "topics": ["taxes"], "people": [], "key_moments": [{"t": 1.0, "label": "Intro"}]}
        return {"result": "ok"}

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        from ..embeddings.hashing import hash_embed

        return [hash_embed(t) for t in texts]
