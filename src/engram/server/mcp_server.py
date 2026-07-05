"""MCP server — any MCP client (Claude Code, Cursor, ...) inherits Engram's memory.

Tools: engram_recall, engram_store, engram_report_outcome, engram_list.
Run stdio:  python -m engram.server.mcp_server
Run SSE:    python -m engram.server.mcp_server --sse   (port 8765)
"""
from __future__ import annotations

import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from engram.memory import recall as recall_mod
from engram.memory.schemas import MEMORY_KINDS, new_id
from engram.memory.store import MemoryStore

mcp = FastMCP("engram", host="0.0.0.0", port=8765)

_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


@mcp.tool()
def engram_recall(
    task: str, domain: str | None = None, budget: int = 1500
) -> dict[str, Any]:
    """Recall memories relevant to a task, packed under a token budget.

    Returns procedures (replayable step recipes), preferences, and episode
    summaries, ranked by relevance x freshness.
    """
    packed = recall_mod.recall(get_store(), task, domain=domain, budget=budget)
    return packed.model_dump(mode="json")


@mcp.tool()
def engram_store(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Store a memory. kind: procedure | preference | episode.

    payload must match the corresponding schema; id is generated if absent.
    """
    model = MEMORY_KINDS.get(kind)
    if model is None:
        return {"error": f"unknown kind: {kind}"}
    if "id" not in payload:
        seed = str(payload.get("task_signature") or payload.get("statement") or payload)
        payload["id"] = new_id(kind[:4], seed)
    memory = model.model_validate(payload)
    get_store().put(memory)  # type: ignore[arg-type]
    return {"stored": memory.id, "kind": kind}  # type: ignore[union-attr]


@mcp.tool()
def engram_report_outcome(
    memory_id: str, success: bool, notes: str | None = None
) -> dict[str, Any]:
    """Report a memory use outcome — updates counts, freshness, and status."""
    return get_store().report_outcome(memory_id, success, notes)


@mcp.tool()
def engram_list(
    kind: str | None = None, min_freshness: float | None = None
) -> list[dict[str, Any]]:
    """List stored memories with lifecycle metadata."""
    return get_store().list(kind=kind, min_freshness=min_freshness)


def main() -> None:
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
