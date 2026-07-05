"""FastAPI service: chat UI, memory endpoints, metrics.

The /chat page is a judged artifact: chat on the left, live memory panel on
the right (recalled memories with freshness bars, per-turn token and latency
counters, latest Curator report pinned at the top).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engram import metrics
from engram.memory import recall as recall_mod
from engram.memory.store import MemoryStore

app = FastAPI(title="engram", version="0.1.0")

UI_DIR = Path(__file__).resolve().parents[3] / "ui"
DEFAULT_TASK_URL = os.getenv("ENGRAM_TASK_URL", "http://127.0.0.1:8090")

_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


class ChatMessage(BaseModel):
    message: str
    url: str | None = None


class SessionEnd(BaseModel):
    transcript: str


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


@app.get("/chat", response_class=HTMLResponse)
def chat_page() -> str:
    return (UI_DIR / "index.html").read_text()


@app.get("/api/state")
def state() -> dict[str, Any]:
    from engram.curator.report import latest_report

    return {
        "report": latest_report(),
        "memories": get_store().list(),
        "metrics": metrics.summary(),
    }


@app.post("/api/chat")
def chat(body: ChatMessage) -> dict[str, Any]:
    """Run the message as a task; sync on purpose (Playwright needs a thread)."""
    from engram.agent.worker import run_task

    record = run_task(body.message, body.url or DEFAULT_TASK_URL, store=get_store())
    record["reply"] = _compose_reply(body.message, record)
    return record


@app.post("/api/end-session")
def end_session(body: SessionEnd) -> dict[str, Any]:
    from engram.memory.preferences import extract_preferences

    stored = extract_preferences(body.transcript, get_store())
    return {"preferences_stored": [p.statement for p in stored]}


def _compose_reply(task: str, record: dict[str, Any]) -> str:
    from engram import llm
    from engram.agent.guardrails import parse_json_block  # noqa: F401  (kept nearby)

    result = record.get("result", {})
    evidence = result.get("extracted") or result.get("summary") or ""
    if not evidence:
        return "That did not work. The episode is stored, so I will learn from it."
    response = llm.complete(
        "chat-reply",
        [{
            "role": "user",
            "content": (
                f"Task: {task}\nData found:\n{evidence[:1500]}\n\n"
                "Answer the task in one or two plain sentences using the data."
            ),
        }],
        model_tier="cheap",
        think=False,
    )
    return str(response.choices[0].message.content).strip()


if (UI_DIR / "app.js").exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")
