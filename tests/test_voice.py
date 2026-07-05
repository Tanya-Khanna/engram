"""Voice endpoints, with the DashScope native calls mocked."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engram.server import api


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "_store", None)
    return TestClient(api.app)


def test_tts_returns_wav_bytes(client, monkeypatch):
    monkeypatch.setattr("engram.voice.tts.speak", lambda text, voice="Cherry": b"RIFFfake")
    response = client.post("/api/tts", json={"text": "hello"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFFfake"


def test_asr_transcribes_posted_bytes(client, monkeypatch):
    seen = {}

    def fake_transcribe(audio: bytes, mime: str = "audio/webm") -> str:
        seen["audio"], seen["mime"] = audio, mime
        return "find flights"

    monkeypatch.setattr("engram.voice.asr.transcribe", fake_transcribe)
    response = client.post(
        "/api/asr", content=b"opusbytes", headers={"Content-Type": "audio/webm"}
    )
    assert response.json() == {"text": "find flights"}
    assert seen == {"audio": b"opusbytes", "mime": "audio/webm"}


def test_transcribe_builds_data_uri(monkeypatch):
    from engram.voice import asr as asr_mod

    captured = {}
    monkeypatch.setattr(asr_mod.llm, "asr", lambda uri: captured.setdefault("uri", uri) and "" or "ok")
    result = asr_mod.transcribe(b"abc", mime="audio/mp4")
    assert result == "ok"
    assert captured["uri"].startswith("data:audio/mp4;base64,")


def test_chat_page_has_mic(client):
    assert 'id="mic"' in client.get("/chat").text
