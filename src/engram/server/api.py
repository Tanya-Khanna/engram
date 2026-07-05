"""FastAPI service: memory + metrics endpoints. /task and /chat land in Phase 2+."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from engram import metrics
from engram.memory import recall as recall_mod
from engram.memory.store import MemoryStore

app = FastAPI(title="engram", version="0.1.0")

_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/memories")
def memories(
    kind: str | None = None, min_freshness: float | None = None
) -> list[dict[str, Any]]:
    return get_store().list(kind=kind, min_freshness=min_freshness)


@app.get("/recall")
def recall(task: str, domain: str | None = None, budget: int = 1500) -> dict[str, Any]:
    return recall_mod.recall(
        get_store(), task, domain=domain, budget=budget
    ).model_dump(mode="json")


@app.get("/metrics")
def metrics_summary(session_id: str | None = None) -> list[dict[str, Any]]:
    return metrics.summary(session_id)


@app.post("/task")
def task() -> None:
    raise HTTPException(status_code=501, detail="worker lands in Phase 2")


@app.get("/chat")
def chat() -> None:
    raise HTTPException(status_code=501, detail="chat UI lands in Phase 4")
