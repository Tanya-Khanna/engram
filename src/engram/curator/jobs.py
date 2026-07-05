"""The Curator: consolidate, decay, reverify, relearn — while you sleep.

Demo mode: `make curator` runs one sweep now. Scheduled mode: --loop MINUTES.
Every sweep produces a human-readable report (report.py).

CLI: python -m engram.curator.jobs [--headed] [--loop MINUTES]
"""
from __future__ import annotations

import argparse
import logging
from typing import Any

from engram.agent import replay as replay_mod, vision_loop
from engram.memory import consolidate as consolidate_mod, decay
from engram.memory.schemas import Episode, Procedure
from engram.memory.store import MemoryStore

logger = logging.getLogger(__name__)


def consolidate_sweep(store: MemoryStore) -> list[dict[str, Any]]:
    """Unconsolidated successful Episodes → Procedures (dedupe by signature)."""
    actions = []
    for row in store.list(kind="episode"):
        episode = store.get(row["id"])
        if not isinstance(episode, Episode) or episode.consolidated:
            continue
        if episode.outcome != "success":
            continue
        procedure = consolidate_mod.consolidate(episode)
        existing = _find_by_signature(store, procedure.task_signature, procedure.domain)
        if existing is not None and existing.id != procedure.id:
            procedure.version = existing.version + 1
            store.put(procedure)
            store.mark_superseded(existing.id, procedure.id)
            actions.append({"job": "consolidate", "id": procedure.id,
                            "note": f"v{procedure.version}, supersedes {existing.id}"})
        elif existing is None:
            store.put(procedure)
            actions.append({"job": "consolidate", "id": procedure.id, "note": "new"})
        episode.consolidated = True
        store.put(episode)
    return actions


def decay_sweep(store: MemoryStore) -> list[dict[str, Any]]:
    """Recompute freshness for all live memories; persist; flag transitions."""
    actions = []
    for row in store.list():
        if row["superseded_by"] or row["kind"] == "episode":
            continue
        memory = store.get(row["id"])
        anchor = getattr(memory, "last_verified", None) or getattr(
            memory, "last_confirmed", None
        )
        if anchor is None:
            continue
        value = decay.freshness(
            kind=memory.kind,
            last_verified=anchor,
            failure_count=getattr(memory, "failure_count", 0),
            success_count=getattr(memory, "success_count", 0),
        )
        old_status = row["status"]
        store.set_freshness(row["id"], value)
        new_status = decay.status(value)
        if new_status != old_status:
            actions.append({"job": "decay", "id": row["id"],
                            "note": f"{old_status} → {new_status} ({value:.2f})"})
    return actions


def reverify_sweep(store: MemoryStore, headless: bool = True) -> list[dict[str, Any]]:
    """Stale procedures → cheap probe replay (no vision loop, one flash check)."""
    actions = []
    for row in store.list(kind="procedure"):
        if row["superseded_by"] or row["status"] != "stale":
            continue
        procedure = store.get(row["id"])
        assert isinstance(procedure, Procedure)
        task = _concrete_task(procedure)
        try:
            replay_mod.replay(procedure, task=task, headless=headless)
            outcome = store.report_outcome(procedure.id, success=True, notes="reverified")
            actions.append({"job": "reverify", "id": procedure.id,
                            "note": f"pass — freshness {outcome['freshness']:.2f}"})
        except replay_mod.ProcedureBroken as exc:
            store.report_outcome(procedure.id, success=False, notes=str(exc))
            # a probe failing against the live site is definitive — straight
            # to the relearn queue, no second opinion needed
            store.set_status(procedure.id, "invalid")
            actions.append({"job": "reverify", "id": procedure.id,
                            "note": f"FAIL ({exc}) — marked invalid"})
    return actions


def relearn_sweep(store: MemoryStore, headless: bool = True) -> list[dict[str, Any]]:
    """Invalid procedures → full vision loop → new version supersedes old."""
    from engram.curator.report import diff_steps

    actions = []
    for row in store.list(kind="procedure"):
        if row["superseded_by"] or row["status"] != "invalid":
            continue
        old = store.get(row["id"])
        assert isinstance(old, Procedure)
        task = _concrete_task(old)
        episode = vision_loop.run_episode(
            task, f"http://{old.domain}/", session_id="curator", headless=headless
        )
        store.put(episode)
        if episode.outcome != "success":
            actions.append({"job": "relearn", "id": old.id,
                            "note": f"relearn FAILED: {episode.summary}"})
            continue
        new = consolidate_mod.consolidate(episode)
        new.version = old.version + 1
        store.put(new)
        episode.consolidated = True
        store.put(episode)
        store.mark_superseded(old.id, new.id)
        diff = diff_steps(old.steps, new.steps)
        actions.append({"job": "relearn", "id": old.id, "new_id": new.id,
                        "note": f"v{new.version} created, v{old.version} archived",
                        "diff": diff,
                        "savings": old.est_cold_tokens - old.est_warm_tokens})
    return actions


def run_sweep(store: MemoryStore | None = None, headless: bool = True) -> dict[str, Any]:
    store = store or MemoryStore()
    return {
        "consolidated": consolidate_sweep(store),
        "decayed": decay_sweep(store),
        "reverified": reverify_sweep(store, headless=headless),
        "relearned": relearn_sweep(store, headless=headless),
    }


def _find_by_signature(
    store: MemoryStore, signature: str, domain: str
) -> Procedure | None:
    for row in store.list(kind="procedure"):
        if row["superseded_by"]:
            continue
        candidate = store.get(row["id"])
        if (
            isinstance(candidate, Procedure)
            and candidate.task_signature == signature
            and candidate.domain == domain
        ):
            return candidate
    return None


def _concrete_task(procedure: Procedure) -> str:
    return replay_mod._substitute(procedure.task_signature, procedure.params) or ""


def age_memories(store: MemoryStore, days: float) -> int:
    """Demo/testing helper: rewind last_verified to simulate elapsed time."""
    from datetime import timedelta

    count = 0
    for row in store.list(kind="procedure"):
        if row["superseded_by"]:
            continue
        memory = store.get(row["id"])
        assert isinstance(memory, Procedure)
        memory.last_verified = memory.last_verified - timedelta(days=days)
        store.put(memory)
        count += 1
    return count


def main() -> None:
    from engram.curator import report as report_mod

    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--loop", type=int, metavar="MINUTES")
    parser.add_argument("--age-days", type=float, metavar="DAYS",
                        help="demo: rewind last_verified and exit")
    args = parser.parse_args()

    if args.age_days:
        count = age_memories(MemoryStore(), args.age_days)
        print(f"aged {count} procedure(s) by {args.age_days} days")
        return

    def sweep_once() -> None:
        sweep = run_sweep(headless=not args.headed)
        text = report_mod.render_report(sweep)
        report_mod.save_report(text)
        print(text)

    if args.loop:
        from apscheduler.schedulers.blocking import BlockingScheduler

        scheduler = BlockingScheduler()
        scheduler.add_job(sweep_once, "interval", minutes=args.loop)
        logger.info("curator loop: every %d min", args.loop)
        scheduler.start()
    else:
        sweep_once()


if __name__ == "__main__":
    main()
