"""Curator sweeps + report, with browser/LLM mocked."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from engram.agent import replay as replay_mod
from engram.curator import jobs, report
from engram.memory.schemas import Episode, Preference, Procedure, Step, new_id
from engram.memory.store import MemoryStore


def _procedure(signature: str = "search flights {origin}->{dest}", days_old: float = 0, **kw) -> Procedure:
    return Procedure(
        id=new_id("proc", signature + str(kw)),
        task_signature=signature,
        domain="127.0.0.1:8090",
        steps=[Step(action="goto", target="http://127.0.0.1:8090/results?from={origin}&to={dest}")],
        params={"origin": "SFO", "dest": "NRT"},
        last_verified=datetime.now(timezone.utc) - timedelta(days=days_old),
        est_cold_tokens=11000,
        est_warm_tokens=1400,
        **kw,
    )


@pytest.fixture
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "store")


def test_decay_sweep_flags_transitions(store):
    store.put(_procedure(days_old=5, success_count=4))   # exp(-.75)≈0.47 → stale
    store.put(_procedure("check prices {origin}", days_old=0, success_count=4))
    actions = jobs.decay_sweep(store)
    notes = " | ".join(a["note"] for a in actions)
    assert "fresh → stale" in notes
    assert len(actions) == 1, "unchanged memories don't appear in the report"


def test_reverify_restores_freshness(store, monkeypatch):
    proc = _procedure(days_old=5, success_count=4)
    store.put(proc)
    jobs.decay_sweep(store)
    monkeypatch.setattr(replay_mod, "replay", lambda *a, **k: {"verified": True})
    actions = jobs.reverify_sweep(store)
    assert len(actions) == 1 and "pass" in actions[0]["note"]
    assert store.get(proc.id).freshness > 0.9


def test_reverify_failure_marks_invalid_then_relearn(store, monkeypatch):
    proc = _procedure(days_old=5, success_count=4, failure_count=1)
    store.put(proc)
    jobs.decay_sweep(store)

    def broken(*a, **k):
        raise replay_mod.ProcedureBroken(0, "selector vanished")

    monkeypatch.setattr(replay_mod, "replay", broken)
    # one hard probe failure against the live site is definitive → invalid
    actions = jobs.reverify_sweep(store)
    assert "marked invalid" in actions[0]["note"]
    assert any(r["status"] == "invalid" for r in store.list(kind="procedure"))

    relearned = _procedure("search flights {origin}->{dest}", days_old=0)
    relearned = relearned.model_copy(update={
        "id": "proc_v2",
        "steps": [Step(action="goto", target="http://127.0.0.1:8090/results?origin={origin}&dest={dest}")],
    })
    episode = Episode(id="ep_rl", session_id="curator", task="t",
                      domain="127.0.0.1:8090", outcome="success")
    monkeypatch.setattr(jobs.vision_loop, "run_episode", lambda *a, **k: episode)
    monkeypatch.setattr(jobs.consolidate_mod, "consolidate", lambda e: relearned)
    actions = jobs.relearn_sweep(store)
    assert actions and actions[0]["new_id"] == "proc_v2"
    assert store.get(proc.id).superseded_by == "proc_v2"
    assert store.get("proc_v2").version == proc.version + 1
    assert any(line.startswith("-") for line in actions[0]["diff"])
    assert any(line.startswith("+") for line in actions[0]["diff"])


def test_consolidate_sweep_marks_episodes(store, monkeypatch):
    episode = Episode(id="ep_c", session_id="s", task="find flights",
                      domain="127.0.0.1:8090", outcome="success", tokens_spent=9000)
    store.put(episode)
    monkeypatch.setattr(jobs.consolidate_mod, "consolidate", lambda e: _procedure("new sig {origin}"))
    actions = jobs.consolidate_sweep(store)
    assert actions and actions[0]["note"] == "new"
    assert store.get("ep_c").consolidated is True
    assert jobs.consolidate_sweep(store) == [], "already-consolidated episodes skipped"


def test_report_renders_relearn_diff():
    sweep = {
        "consolidated": [],
        "decayed": [{"job": "decay", "id": "proc_a", "note": "fresh → stale (0.55)"}],
        "reverified": [{"job": "reverify", "id": "proc_a", "note": "FAIL (step 0) — status invalid"}],
        "relearned": [{
            "job": "relearn", "id": "proc_a", "new_id": "proc_b",
            "note": "v2 created, v1 archived",
            "diff": ["- goto http://x/results?from={origin}", "+ goto http://x/results?origin={origin}"],
            "savings": 9600,
        }],
    }
    text = report.render_report(sweep)
    assert "🌙" in text and "1 relearned" in text
    assert "- goto" in text and "+ goto" in text
    assert "9,600 tokens/run" in text


def test_preference_contradiction_lowers_confidence(store, monkeypatch):
    from engram.memory import preferences as prefs_mod
    from types import SimpleNamespace

    old = Preference(id=new_id("pref", "aisle"), statement="prefers window seats")
    store.put(old)
    reply = '{"preferences": [{"statement": "prefers aisle seats", "evidence": "aisle please"}]}'
    monkeypatch.setattr(
        prefs_mod.llm, "complete",
        lambda *a, **k: SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2,
                                  completion_tokens_details=None),
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
        ),
    )
    stored = prefs_mod.extract_preferences("user: aisle please", store)
    assert stored[0].contradicts == old.id
    assert store.get(old.id).confidence < 0.6
