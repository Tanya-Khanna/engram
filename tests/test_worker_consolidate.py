"""Worker orchestration + consolidation, with LLM and browser mocked."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from engram.agent import replay as replay_mod, worker
from engram.memory import consolidate as consolidate_mod
from engram.memory.schemas import Episode, Procedure, Step, new_id
from engram.memory.store import MemoryStore


def _llm_reply(text: str):
    return SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=10, completion_tokens=10, total_tokens=20,
            completion_tokens_details=None,
        ),
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
    )


def _procedure() -> Procedure:
    return Procedure(
        id=new_id("proc", "flights"),
        task_signature="search flights {origin}->{dest} {date}",
        domain="127.0.0.1:8090",
        steps=[Step(action="goto", target="http://127.0.0.1:8090/results?from={origin}&to={dest}&date={date}")],
        params={"origin": "SFO", "dest": "NRT", "date": "2026-07-20"},
    )


@pytest.fixture
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "store")


def test_consolidate_valid_first_try(monkeypatch):
    draft = (
        '{"task_signature": "search flights {origin}->{dest} {date}",'
        ' "steps": [{"action": "goto", "target": "http://x/results?from={origin}"}],'
        ' "params": {"origin": "SFO"}, "preconditions": []}'
    )
    monkeypatch.setattr(consolidate_mod.llm, "complete", MagicMock(return_value=_llm_reply(draft)))
    episode = Episode(id="ep_1", session_id="s", task="t", domain="x", tokens_spent=1234)
    procedure = consolidate_mod.consolidate(episode)
    assert procedure.est_cold_tokens == 1234
    assert procedure.steps[0].action == "goto"
    assert procedure.created_from == "ep_1"


def test_consolidate_retries_on_invalid(monkeypatch):
    bad = '{"task_signature": "x", "steps": [{"action": "teleport", "target": "y"}]}'
    good = '{"task_signature": "x", "steps": [{"action": "goto", "target": "http://y"}], "params": {}}'
    mock = MagicMock(side_effect=[_llm_reply(bad), _llm_reply(good)])
    monkeypatch.setattr(consolidate_mod.llm, "complete", mock)
    episode = Episode(id="ep_2", session_id="s", task="t", domain="x")
    procedure = consolidate_mod.consolidate(episode)
    assert mock.call_count == 2
    assert procedure.steps[0].action == "goto"


def test_warm_path_reports_success(store, monkeypatch):
    proc = _procedure()
    store.put(proc)
    monkeypatch.setattr(worker, "_extract_params", lambda task, p: p.params)
    monkeypatch.setattr(
        replay_mod, "replay",
        lambda *a, **k: {"extracted": "flights!", "verified": True, "seconds": 1.0},
    )
    record = worker.run_task("find flights SFO to NRT", "http://127.0.0.1:8090/", store=store)
    assert record["path"] == "warm"
    assert store.get(proc.id).success_count == 1


def test_broken_procedure_falls_through_to_cold(store, monkeypatch):
    proc = _procedure()
    store.put(proc)
    monkeypatch.setattr(worker, "_extract_params", lambda task, p: p.params)

    def broken(*a, **k):
        raise replay_mod.ProcedureBroken(0, "selector vanished")

    monkeypatch.setattr(replay_mod, "replay", broken)
    episode = Episode(
        id="ep_cold", session_id="s", task="find flights", domain="127.0.0.1:8090",
        outcome="success", tokens_spent=9000,
    )
    relearned = _procedure().model_copy(update={"id": "proc_relearned_v2"})
    monkeypatch.setattr(worker.vision_loop, "run_episode", lambda *a, **k: episode)
    monkeypatch.setattr(worker.consolidate_mod, "consolidate", lambda e: relearned)

    record = worker.run_task("find flights", "http://127.0.0.1:8090/", store=store)
    assert record["path"] == "cold"
    assert record["episode"] == "ep_cold"
    assert store.get(proc.id).failure_count == 1
    assert store.get(proc.id).superseded_by == "proc_relearned_v2"


def test_replay_substitutes_params():
    assert replay_mod._substitute("/r?from={origin}&to={dest}", {"origin": "SFO", "dest": "NRT"}) == "/r?from=SFO&to=NRT"
    assert replay_mod._substitute(None, {"a": "b"}) is None
