"""Orchestrator: recall → replay (warm) | explore + consolidate (cold).

Every run returns a cost record {path, tokens, seconds, ...} — these feed the
bench charts and the live demo counters.

CLI: python -m engram.agent.worker --task "..." --url http://127.0.0.1:8090
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any

from engram import llm
from engram.agent import guardrails, replay as replay_mod, vision_loop
from engram.memory import consolidate as consolidate_mod
from engram.memory.decay import STALE_THRESHOLD
from engram.memory.recall import recall
from engram.memory.schemas import Procedure
from engram.memory.store import MemoryStore


def run_task(
    task: str,
    start_url: str,
    store: MemoryStore | None = None,
    force_cold: bool = False,
    headless: bool = True,
) -> dict[str, Any]:
    store = store or MemoryStore()
    domain = vision_loop._domain(start_url)
    start = time.monotonic()
    tokens_before = _session_tokens()

    broken_id: str | None = None
    recalled: list[dict[str, Any]] = []
    if not force_cold:
        hit, recalled = _best_procedure(store, task, domain)
        if hit is not None:
            try:
                params = _extract_params(task, hit)
                result = replay_mod.replay(hit, params=params, task=task, headless=headless)
                store.report_outcome(hit.id, success=True)
                return _record("warm", task, start, tokens_before, result=result,
                               procedure=hit.id, recalled=recalled)
            except replay_mod.ProcedureBroken as exc:
                store.report_outcome(hit.id, success=False, notes=str(exc))
                broken_id = hit.id
                # fall THROUGH to cold — resilience is the demo

    episode = vision_loop.run_episode(
        task, start_url, headless=headless,
        extra_context=_preference_context(store, task),
    )
    store.put(episode)
    procedure_id = None
    if episode.outcome == "success":
        procedure = consolidate_mod.consolidate(episode)
        store.put(procedure)
        procedure_id = procedure.id
        episode.consolidated = True
        store.put(episode)
        if broken_id and broken_id != procedure.id:
            store.mark_superseded(broken_id, procedure.id)
    return _record(
        "cold", task, start, tokens_before,
        result={"outcome": episode.outcome, "summary": episode.summary},
        episode=episode.id, procedure=procedure_id, recalled=recalled,
    )


def _preference_context(store: MemoryStore, task: str) -> str | None:
    packed = recall(store, task, kinds=("preference",), budget=200)
    if not packed.items:
        return None
    return "Known user preferences:\n" + "\n".join(i.text for i in packed.items)


def _best_procedure(
    store: MemoryStore, task: str, domain: str
) -> tuple[Procedure | None, list[dict[str, Any]]]:
    """Best fresh hit plus what was recalled (the UI sidebar shows this)."""
    packed = recall(store, task, domain=domain, kinds=("procedure",), budget=4000)
    recalled = [
        {"id": i.memory_id, "kind": i.kind, "freshness": round(i.freshness, 3),
         "score": i.score}
        for i in packed.items
    ]
    for item in packed.items:
        if item.freshness >= STALE_THRESHOLD:
            memory = store.get(item.memory_id)
            if isinstance(memory, Procedure):
                return memory, recalled
    return None, recalled


def _extract_params(task: str, procedure: Procedure) -> dict[str, str]:
    """One flash call maps the concrete task onto the procedure's placeholders."""
    if not procedure.params:
        return {}
    response = llm.complete(
        "param-extraction",
        [
            {
                "role": "user",
                "content": (
                    f"Task: {task}\nProcedure signature: {procedure.task_signature}\n"
                    f"Example params from a previous run: {json.dumps(procedure.params)}\n"
                    "Extract the values for the SAME param names from this task."
                    " Reply with strict JSON only, same keys."
                ),
            }
        ],
        model_tier="cheap",
        think=False,
    )
    extracted = guardrails.parse_json_block(response.choices[0].message.content)
    return {k: str(v) for k, v in extracted.items() if k in procedure.params}


def _session_tokens() -> int:
    from engram import metrics

    return sum(
        row["prompt_tokens"] + row["completion_tokens"]
        for row in metrics.summary(llm.SESSION_ID)
    )


def _record(
    path: str, task: str, start: float, tokens_before: int, **extra: Any
) -> dict[str, Any]:
    return {
        "path": path,
        "task": task,
        "seconds": round(time.monotonic() - start, 2),
        "tokens": _session_tokens() - tokens_before,
        **extra,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--force-cold", action="store_true")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    record = run_task(
        args.task, args.url, force_cold=args.force_cold, headless=not args.headed
    )
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
