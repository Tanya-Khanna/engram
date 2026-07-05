"""Memory record schemas. The Procedure is the heart of the project."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:12]}"


class Step(BaseModel):
    action: Literal["goto", "click", "fill", "press", "extract", "wait_for"]
    target: str            # URL, CSS/aria selector, or key
    value: str | None = None
    fallback_selector: str | None = None


class Procedure(BaseModel):
    id: str                       # proc_<hash>
    kind: Literal["procedure"] = "procedure"
    task_signature: str           # normalized intent, e.g. "search flights {origin}->{dest} {date}"
    domain: str                   # e.g. flights.local, news.ycombinator.com
    steps: list[Step]
    params: dict[str, str] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    freshness: float = 1.0        # 0..1, decayed by Curator
    success_count: int = 0
    failure_count: int = 0
    last_verified: datetime = Field(default_factory=utcnow)
    last_used: datetime = Field(default_factory=utcnow)
    created_from: str = ""        # episode id (provenance)
    est_cold_tokens: int = 0      # what this memory SAVES
    est_warm_tokens: int = 0
    version: int = 1
    superseded_by: str | None = None

    def embed_text(self) -> str:
        return f"{self.task_signature} {self.domain}"

    def compact_text(self) -> str:
        """Dense serialization for budgeted context packing."""
        steps = ";".join(
            "|".join(filter(None, (s.action, s.target, s.value))) for s in self.steps
        )
        return (
            f"[procedure {self.id} v{self.version} domain={self.domain}"
            f" fresh={self.freshness:.2f}] {self.task_signature}"
            f" params={json.dumps(self.params, separators=(',', ':'))}"
            f" steps={steps}"
        )


class Preference(BaseModel):
    id: str
    kind: Literal["preference"] = "preference"
    user_id: str = "default"
    statement: str                # e.g. "prefers aisle seats"
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.6
    freshness: float = 1.0
    last_confirmed: datetime = Field(default_factory=utcnow)
    contradicts: str | None = None

    def embed_text(self) -> str:
        return self.statement

    def compact_text(self) -> str:
        return f"[preference conf={self.confidence:.2f}] {self.statement}"


class Episode(BaseModel):
    id: str
    kind: Literal["episode"] = "episode"
    session_id: str
    task: str
    domain: str = ""
    trajectory: list[dict[str, Any]] = Field(default_factory=list)
    screenshots_dir: str | None = None
    outcome: Literal["success", "failure", "aborted"] = "success"
    tokens_spent: int = 0
    summary: str = ""
    consolidated: bool = False
    freshness: float = 1.0
    created_at: datetime = Field(default_factory=utcnow)

    def embed_text(self) -> str:
        return f"{self.task} {self.domain}"

    def compact_text(self) -> str:
        return f"[episode {self.outcome}] {self.task}: {self.summary or '(no summary)'}"


Memory = Procedure | Preference | Episode

MEMORY_KINDS: dict[str, type[BaseModel]] = {
    "procedure": Procedure,
    "preference": Preference,
    "episode": Episode,
}


class PackedItem(BaseModel):
    memory_id: str
    kind: str
    text: str
    score: float
    freshness: float


class PackedContext(BaseModel):
    items: list[PackedItem]
    tokens_used: int
    dropped: list[str]            # memory ids that didn't fit the budget
