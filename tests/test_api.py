"""API endpoints, with the worker and LLM mocked."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from engram.server import api


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_store", None)
    return TestClient(api.app)


def test_chat_page_serves_sidebar(client):
    page = client.get("/chat")
    assert page.status_code == 200
    assert 'id="recalled"' in page.text
    assert 'id="report"' in page.text


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_api_chat_returns_record_and_reply(client, monkeypatch):
    record = {
        "path": "warm", "task": "t", "seconds": 2.1, "tokens": 460,
        "result": {"extracted": "EV793 $998"}, "procedure": "proc_x",
        "recalled": [{"id": "proc_x", "kind": "procedure", "freshness": 0.9, "score": 0.8}],
    }
    monkeypatch.setattr("engram.agent.worker.run_task", lambda *a, **k: dict(record))
    monkeypatch.setattr(
        api, "_compose_reply", lambda task, rec: "Cheapest is EV793 at $998."
    )
    response = client.post("/api/chat", json={"message": "find flights"})
    body = response.json()
    assert body["reply"] == "Cheapest is EV793 at $998."
    assert body["recalled"][0]["id"] == "proc_x"


def test_state_includes_report_and_memories(client, monkeypatch, tmp_path):
    from engram.curator import report

    report.save_report("🌙 Curator run test · 1 verified")
    body = client.get("/api/state").json()
    assert "Curator run test" in body["report"]
    assert isinstance(body["memories"], list)


def test_end_session_extracts_preferences(client, monkeypatch):
    monkeypatch.setattr(
        "engram.memory.preferences.extract_preferences",
        lambda transcript, store: [SimpleNamespace(statement="prefers aisle seats")],
    )
    body = client.post("/api/end-session", json={"transcript": "user: aisle please"}).json()
    assert body["preferences_stored"] == ["prefers aisle seats"]
