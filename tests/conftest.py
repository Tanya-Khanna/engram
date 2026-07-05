from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets its own data dir, hash embeddings, and no real API key."""
    monkeypatch.setenv("ENGRAM_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("ENGRAM_EMBEDDINGS", "hash")
    monkeypatch.delenv("QDRANT_URL", raising=False)
    yield
