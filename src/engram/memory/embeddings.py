"""Embedding interface with a fallback chain, behind one function.

Order: DashScope (primary) → local bge-small (if sentence-transformers is
installed) → deterministic hash vectors (offline dev/tests only).
Select explicitly with ENGRAM_EMBEDDINGS=dashscope|local|hash (default: auto).
"""
from __future__ import annotations

import hashlib
import logging
import math
import os

logger = logging.getLogger(__name__)

HASH_DIM = 256

_local_model = None
_active_backend: str | None = None


def _hash_vector(text: str) -> list[float]:
    """Deterministic pseudo-embedding — keeps offline dev running, never prod."""
    vec = [0.0] * HASH_DIM
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode()).digest()
        for i in range(0, 32, 4):
            idx = int.from_bytes(digest[i : i + 2], "big") % HASH_DIM
            sign = 1 if digest[i + 2] % 2 else -1
            vec[idx] += sign * (digest[i + 3] / 255)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _embed_local(texts: list[str]) -> list[list[float]]:
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer  # lazy heavy import

        _local_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return [list(map(float, v)) for v in _local_model.encode(texts)]


def _embed_dashscope(texts: list[str]) -> list[list[float]]:
    from engram import llm

    return llm.embed(texts)


def active_backend() -> str | None:
    return _active_backend


def embed_texts(texts: list[str]) -> list[list[float]]:
    global _active_backend
    mode = os.getenv("ENGRAM_EMBEDDINGS", "auto")
    if mode == "hash":
        _active_backend = "hash"
        return [_hash_vector(t) for t in texts]
    if mode == "local":
        _active_backend = "local"
        return _embed_local(texts)
    if mode == "dashscope":
        _active_backend = "dashscope"
        return _embed_dashscope(texts)

    # auto: DashScope → local → hash
    try:
        result = _embed_dashscope(texts)
        _active_backend = "dashscope"
        return result
    except Exception as exc:  # noqa: BLE001 — any failure falls through
        logger.warning("DashScope embeddings unavailable (%s); falling back", exc)
    try:
        result = _embed_local(texts)
        _active_backend = "local"
        return result
    except Exception:  # noqa: BLE001
        logger.warning("local bge unavailable; using hash vectors (dev only)")
        _active_backend = "hash"
        return [_hash_vector(t) for t in texts]
