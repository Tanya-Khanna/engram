"""Hybrid memory store: Qdrant for vectors, SQLite for metadata.

Qdrant resolution: QDRANT_URL if reachable, else embedded local mode under
the data dir (laptop dev); the ECS deployment runs the docker service.
SQLite mirrors all lifecycle metadata for filtering, the Curator's sweeps,
and the metrics dashboard.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from engram import metrics
from engram.memory import decay, embeddings
from engram.memory.schemas import MEMORY_KINDS, Memory, utcnow

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL,
    freshness REAL NOT NULL DEFAULT 1.0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'fresh',
    last_verified TEXT,
    last_used TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    superseded_by TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _point_id(memory_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, memory_id))


class MemoryStore:
    def __init__(
        self,
        qdrant_url: str | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.data_dir = data_dir or metrics.data_dir()
        self.qdrant = self._connect_qdrant(qdrant_url or os.getenv("QDRANT_URL"))
        self._dims: dict[str, int] = {}
        self.db = sqlite3.connect(self.data_dir / "engram.db")
        self.db.row_factory = sqlite3.Row
        self.db.execute(_SCHEMA)
        self.db.commit()

    def _connect_qdrant(self, url: str | None) -> QdrantClient:
        if url:
            try:
                client = QdrantClient(url=url, timeout=5)
                client.get_collections()
                return client
            except Exception:  # noqa: BLE001 — any connectivity failure
                logger.warning("qdrant at %s unreachable; using embedded mode", url)
        return QdrantClient(path=str(self.data_dir / "qdrant"))

    def _ensure_collection(self, kind: str, dim: int) -> None:
        if self._dims.get(kind) == dim:
            return
        if not self.qdrant.collection_exists(kind):
            self.qdrant.create_collection(
                kind, vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
            )
        self._dims[kind] = dim

    # -- writes ------------------------------------------------------------

    def put(self, memory: Memory) -> None:
        vector = embeddings.embed_texts([memory.embed_text()])[0]
        self._ensure_collection(memory.kind, len(vector))
        payload = memory.model_dump(mode="json")
        self.qdrant.upsert(
            memory.kind,
            [PointStruct(id=_point_id(memory.id), vector=vector, payload=payload)],
        )
        row = {
            "id": memory.id,
            "kind": memory.kind,
            "domain": getattr(memory, "domain", ""),
            "label": memory.embed_text(),
            "freshness": memory.freshness,
            "success_count": getattr(memory, "success_count", 0),
            "failure_count": getattr(memory, "failure_count", 0),
            "last_verified": _iso(getattr(memory, "last_verified", None)),
            "last_used": _iso(getattr(memory, "last_used", None)),
            "version": getattr(memory, "version", 1),
            "superseded_by": getattr(memory, "superseded_by", None),
            "payload": json.dumps(payload),
            "created_at": utcnow().isoformat(),
        }
        with self.db:
            self.db.execute(
                """INSERT INTO memories (id, kind, domain, label, freshness,
                       success_count, failure_count, last_verified, last_used,
                       version, superseded_by, payload, created_at)
                   VALUES (:id, :kind, :domain, :label, :freshness,
                       :success_count, :failure_count, :last_verified, :last_used,
                       :version, :superseded_by, :payload, :created_at)
                   ON CONFLICT(id) DO UPDATE SET
                       label=:label, freshness=:freshness,
                       success_count=:success_count, failure_count=:failure_count,
                       last_verified=:last_verified, last_used=:last_used,
                       version=:version, superseded_by=:superseded_by,
                       payload=:payload""",
                row,
            )

    def report_outcome(
        self, memory_id: str, success: bool, notes: str | None = None
    ) -> dict[str, Any]:
        """Update counts + freshness after a use; may flip status to invalid."""
        memory = self.get(memory_id)
        row = self._row(memory_id)
        now = datetime.now(timezone.utc)
        consecutive = 0 if success else row["consecutive_failures"] + 1
        memory.success_count += 1 if success else 0
        memory.failure_count += 0 if success else 1
        memory.last_used = now
        if success:
            memory.last_verified = now
        memory.freshness = decay.freshness(
            kind=memory.kind,
            last_verified=memory.last_verified,
            failure_count=memory.failure_count,
            success_count=memory.success_count,
            now=now,
        )
        new_status = decay.status(memory.freshness, consecutive)
        self.put(memory)
        with self.db:
            self.db.execute(
                "UPDATE memories SET consecutive_failures=?, status=? WHERE id=?",
                (consecutive, new_status, memory_id),
            )
        return {
            "id": memory_id,
            "status": new_status,
            "freshness": memory.freshness,
            "consecutive_failures": consecutive,
            "notes": notes,
        }

    def set_freshness(self, memory_id: str, value: float) -> None:
        memory = self.get(memory_id)
        memory.freshness = value
        self.put(memory)
        with self.db:
            self.db.execute(
                "UPDATE memories SET status=? WHERE id=?",
                (decay.status(value, self._row(memory_id)["consecutive_failures"]),
                 memory_id),
            )

    def set_status(self, memory_id: str, status: str) -> None:
        with self.db:
            self.db.execute(
                "UPDATE memories SET status=? WHERE id=?", (status, memory_id)
            )

    def mark_superseded(self, old_id: str, new_id: str) -> None:
        memory = self.get(old_id)
        memory.superseded_by = new_id
        self.put(memory)

    # -- reads -------------------------------------------------------------

    def _row(self, memory_id: str) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM memories WHERE id=?", (memory_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"memory not found: {memory_id}")
        return row

    def get(self, memory_id: str) -> Memory:
        row = self._row(memory_id)
        model = MEMORY_KINDS[row["kind"]]
        return model.model_validate_json(row["payload"])  # type: ignore[return-value]

    def list(
        self, kind: str | None = None, min_freshness: float | None = None
    ) -> list[dict[str, Any]]:
        clauses, args = ["1=1"], []
        if kind:
            clauses.append("kind=?")
            args.append(kind)
        if min_freshness is not None:
            clauses.append("freshness>=?")
            args.append(min_freshness)
        rows = self.db.execute(
            "SELECT id, kind, domain, label, freshness, status, success_count,"
            " failure_count, version, superseded_by FROM memories"
            f" WHERE {' AND '.join(clauses)} ORDER BY freshness DESC",
            args,
        ).fetchall()
        return [dict(r) for r in rows]

    def search(
        self, query: str, kind: str, top_k: int = 10
    ) -> list[tuple[Memory, float]]:
        """Vector search → [(memory, cosine score)]. Empty if no collection."""
        if not self.qdrant.collection_exists(kind):
            return []
        vector = embeddings.embed_texts([query])[0]
        hits = self.qdrant.query_points(kind, query=vector, limit=top_k).points
        results: list[tuple[Memory, float]] = []
        for hit in hits:
            model = MEMORY_KINDS[kind]
            results.append((model.model_validate(hit.payload), float(hit.score)))
        return results


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
