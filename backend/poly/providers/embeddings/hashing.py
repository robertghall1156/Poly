"""Deterministic hashing embeddings — a local, model-free fallback.

Semantic search is much better with a real local embedding model (e.g. `ollama pull
nomic-embed-text`). Until one is available, this feature-hashing bag-of-words + character n-gram
vector keeps search working (lexical similarity only). Vectors are 768-d, unit-normalised, and
tagged with model name `hashing-v1` so they are re-embedded when a real model appears.
"""
from __future__ import annotations

import hashlib
import math
import re

from ...models import EMBEDDING_DIM
from ..base import EmbeddingProvider

_TOKEN = re.compile(r"[a-z0-9]+")
MODEL_NAME = "hashing-v1"


def _bucket(token: str) -> tuple[int, float]:
    h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    idx = int.from_bytes(h[:4], "little") % EMBEDDING_DIM
    sign = 1.0 if h[4] & 1 else -1.0
    return idx, sign


def hash_embed(text: str) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    tokens = _TOKEN.findall(text.lower())
    for tok in tokens:
        idx, sign = _bucket(tok)
        vec[idx] += sign
        if len(tok) >= 5:
            for i in range(len(tok) - 3):
                idx2, sign2 = _bucket("#" + tok[i : i + 4])
                vec[idx2] += 0.3 * sign2
    for a, b in zip(tokens, tokens[1:]):
        idx, sign = _bucket(a + "_" + b)
        vec[idx] += 0.5 * sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class HashingEmbeddingProvider(EmbeddingProvider):
    name = "hashing"
    locality = "local"
    dimension = EMBEDDING_DIM

    def embed(self, texts: list[str], *, model: str = MODEL_NAME) -> list[list[float]]:
        return [hash_embed(t) for t in texts]

    def health(self) -> bool:
        return True
