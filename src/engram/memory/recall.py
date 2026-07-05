"""Hybrid retrieval + budget-aware context packing.

Fused score: 0.55*vector + 0.25*domain + 0.20*keyword, then multiplied by
(0.5 + 0.5*freshness) — stale memories rank down but never rank-zero, so the
Curator can still find them.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from engram.memory.schemas import Memory, PackedContext, PackedItem
from engram.memory.store import MemoryStore

DEFAULT_BUDGET = 1500
VEC_W, DOMAIN_W, KW_W = 0.55, 0.25, 0.20
_CHARS_PER_TOKEN = 4  # cheap approximation; real counts come from the API meter


def approx_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN + 1


def _fused_score(memory: Memory, vec_score: float, query: str, domain: str | None) -> float:
    domain_score = 1.0 if domain and getattr(memory, "domain", "") == domain else 0.0
    kw_score = fuzz.token_set_ratio(query, memory.embed_text()) / 100
    fused = VEC_W * vec_score + DOMAIN_W * domain_score + KW_W * kw_score
    return fused * (0.5 + 0.5 * memory.freshness)


def recall(
    store: MemoryStore,
    query: str,
    domain: str | None = None,
    budget: int = DEFAULT_BUDGET,
    strategy: str = "packed",
    kinds: tuple[str, ...] = ("procedure", "preference", "episode"),
    top_k: int = 5,
) -> PackedContext:
    """Retrieve, rank, and pack memories under a token budget.

    strategy="packed": greedy fill of the budget with compact serializations.
    strategy="topk": naive top-k with full JSON payloads (the bench baseline).
    """
    scored: list[tuple[float, Memory]] = []
    for kind in kinds:
        for memory, vec_score in store.search(query, kind):
            if getattr(memory, "superseded_by", None):
                continue
            scored.append((_fused_score(memory, vec_score, query, domain), memory))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    if strategy == "topk":
        chosen = scored[:top_k]
        items = [
            PackedItem(
                memory_id=m.id,
                kind=m.kind,
                text=m.model_dump_json(),
                score=round(score, 4),
                freshness=m.freshness,
            )
            for score, m in chosen
        ]
        return PackedContext(
            items=items,
            tokens_used=sum(approx_tokens(i.text) for i in items),
            dropped=[m.id for _, m in scored[top_k:]],
        )

    items = []
    dropped = []
    tokens_used = 0
    for score, memory in scored:
        text = memory.compact_text()
        cost = approx_tokens(text)
        if tokens_used + cost > budget:
            dropped.append(memory.id)
            continue
        tokens_used += cost
        items.append(
            PackedItem(
                memory_id=memory.id,
                kind=memory.kind,
                text=text,
                score=round(score, 4),
                freshness=memory.freshness,
            )
        )
    return PackedContext(items=items, tokens_used=tokens_used, dropped=dropped)
