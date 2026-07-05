"""Token/latency logging for every LLM call — JSONL + SQLite.

Benchmarks, charts, and the live demo counters all read from here, so this
module must stay dependency-free and never raise into the calling path.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    session_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL
);
"""


def data_dir() -> Path:
    d = Path(os.getenv("ENGRAM_DATA_DIR", "var"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(data_dir() / "engram.db")
    conn.execute(_SCHEMA)
    return conn


def log_call(
    *,
    purpose: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    session_id: str,
    reasoning_tokens: int = 0,
) -> dict[str, Any]:
    """Record one LLM call to both the JSONL stream and the SQLite mirror."""
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "purpose": purpose,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "latency_ms": round(latency_ms, 1),
    }
    with _LOCK:
        with open(data_dir() / "metrics.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
        with _db() as conn:
            conn.execute(
                "INSERT INTO llm_calls (ts, session_id, purpose, model, prompt_tokens,"
                " completion_tokens, reasoning_tokens, latency_ms)"
                " VALUES (:ts, :session_id, :purpose, :model, :prompt_tokens,"
                " :completion_tokens, :reasoning_tokens, :latency_ms)",
                record,
            )
    return record


def summary(session_id: str | None = None) -> list[dict[str, Any]]:
    """Aggregate calls by purpose+model — feeds /metrics and the bench charts."""
    where = "WHERE session_id = ?" if session_id else ""
    args = (session_id,) if session_id else ()
    with _db() as conn:
        rows = conn.execute(
            f"""SELECT purpose, model, COUNT(*) AS calls,
                   SUM(prompt_tokens) AS prompt_tokens,
                   SUM(completion_tokens) AS completion_tokens,
                   SUM(reasoning_tokens) AS reasoning_tokens,
                   ROUND(AVG(latency_ms), 1) AS avg_latency_ms
                FROM llm_calls {where}
                GROUP BY purpose, model ORDER BY calls DESC""",
            args,
        ).fetchall()
    cols = [
        "purpose", "model", "calls", "prompt_tokens",
        "completion_tokens", "reasoning_tokens", "avg_latency_ms",
    ]
    return [dict(zip(cols, r)) for r in rows]
