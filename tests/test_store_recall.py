"""Store round-trip + recall packing under budget (Phase 1 acceptance tests)."""
from __future__ import annotations

import pytest

from engram.memory.recall import recall
from engram.memory.schemas import Preference, Procedure, Step, new_id
from engram.memory.store import MemoryStore


def _procedure(signature: str, domain: str = "flights.local", **kw) -> Procedure:
    return Procedure(
        id=new_id("proc", signature),
        task_signature=signature,
        domain=domain,
        steps=[
            Step(action="goto", target=f"http://{domain}/"),
            Step(action="fill", target="#origin", value="{origin}"),
            Step(action="click", target="#search", fallback_selector="button[type=submit]"),
            Step(action="extract", target="table.results"),
        ],
        params={"origin": "SFO", "dest": "NRT"},
        **kw,
    )


@pytest.fixture
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "store")


def test_store_recall_round_trip(store):
    proc = _procedure("search flights {origin}->{dest} {date}")
    store.put(proc)

    packed = recall(store, "search flights SFO to Tokyo", domain="flights.local")
    assert packed.items, "stored procedure was not recalled"
    assert packed.items[0].memory_id == proc.id
    assert "search flights" in packed.items[0].text
    assert store.get(proc.id).steps == proc.steps


def test_budget_forces_drops(store):
    for i in range(6):
        store.put(_procedure(f"search flights variant {i} {'x' * 200}"))
    packed = recall(store, "search flights", budget=200)
    assert packed.dropped, "budget=200 should force drops"
    assert packed.tokens_used <= 200
    assert len(packed.items) + len(packed.dropped) == 6


def test_stale_ranks_below_fresh(store):
    fresh = _procedure("check flight prices", freshness=1.0)
    stale = _procedure("check flight status", freshness=0.1)
    store.put(fresh)
    store.put(stale)
    packed = recall(store, "check flight", budget=4000)
    ids = [i.memory_id for i in packed.items]
    assert ids.index(fresh.id) < ids.index(stale.id)
    assert stale.id in ids, "stale memories rank down but never rank-zero"


def test_superseded_never_recalled(store):
    old = _procedure("book hotel")
    store.put(old)
    store.mark_superseded(old.id, "proc_newversion")
    packed = recall(store, "book hotel", budget=4000)
    assert all(i.memory_id != old.id for i in packed.items)


def test_topk_strategy_baseline(store):
    for i in range(4):
        store.put(_procedure(f"task number {i}"))
    packed = recall(store, "task", strategy="topk", top_k=2)
    assert len(packed.items) == 2
    assert packed.items[0].text.startswith("{")  # full JSON, not compact


def test_report_outcome_lifecycle(store):
    proc = _procedure("search flights")
    store.put(proc)

    ok = store.report_outcome(proc.id, success=True)
    assert ok["status"] == "fresh"
    assert ok["consecutive_failures"] == 0

    store.report_outcome(proc.id, success=False)
    bad = store.report_outcome(proc.id, success=False)
    assert bad["consecutive_failures"] == 2
    assert bad["status"] == "invalid"


def test_preferences_pack_as_one_liners(store):
    store.put(
        Preference(id=new_id("pref", "aisle"), statement="prefers aisle seats")
    )
    packed = recall(store, "prefers aisle seats", kinds=("preference",))
    assert packed.items
    assert packed.items[0].text == "[preference conf=0.60] prefers aisle seats"
