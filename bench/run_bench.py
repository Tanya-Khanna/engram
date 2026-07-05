"""Benchmark runner → CSVs in bench/out/. Charts come from charts.py.

Suites:
  coldwarm  — each task cold once, then warm ×3 (REAL runs; needs demo-site)
  recall    — accuracy under budget, packed vs topk, 35-memory store
  lifecycle — simulated-clock freshness timeline of one procedure

Usage: python bench/run_bench.py [coldwarm|recall|lifecycle|all]
"""
from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("ENGRAM_DATA_DIR", "var/bench")

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

WARM_REPEATS = 3
BUDGETS = (500, 1500, 4000)


def _tasks() -> list[dict[str, str]]:
    import yaml

    spec = yaml.safe_load((Path(__file__).resolve().parent / "tasks.yaml").read_text())
    return spec["tasks"]


def suite_coldwarm() -> None:
    from engram.agent.worker import run_task
    from engram.memory.store import MemoryStore

    store = MemoryStore()
    rows = []
    for spec in _tasks():
        print(f"[coldwarm] {spec['id']} cold ...", flush=True)
        cold = run_task(spec["task"], spec["url"], store=store, force_cold=True)
        rows.append({"task": spec["id"], "path": "cold", "run": 0,
                     "seconds": cold["seconds"], "tokens": cold["tokens"],
                     "outcome": cold["result"].get("outcome", "success")})
        for i in range(1, WARM_REPEATS + 1):
            print(f"[coldwarm] {spec['id']} warm {i} ...", flush=True)
            warm = run_task(spec["task"], spec["url"], store=store)
            rows.append({"task": spec["id"], "path": warm["path"], "run": i,
                         "seconds": warm["seconds"], "tokens": warm["tokens"],
                         "outcome": "success" if warm["path"] == "warm" else "fell-through"})
    _write("coldwarm.csv", rows)


def suite_recall() -> None:
    os.environ["ENGRAM_DATA_DIR"] = "var/bench_recall"
    from engram.memory.recall import recall
    from engram.memory.schemas import Procedure, Step, new_id
    from engram.memory.store import MemoryStore

    store = MemoryStore(data_dir=Path("var/bench_recall"))
    domains = ["flights.local", "books.example", "news.example", "shop.example",
               "mail.example", "cal.example", "docs.example"]
    # 5 near-duplicate variants per domain share vocabulary, so ranking is
    # noisy and the target does not trivially sit at rank 1
    variants = ["for the {date} deadline", "sorted by price {date}",
                "in the {date} report view", "filtered to {date} only",
                "grouped weekly around {date}"]
    # realistic step count → full-JSON payloads are genuinely large
    def _steps(domain: str) -> list[Step]:
        return [
            Step(action="goto", target=f"http://{domain}/app?d={{date}}"),
            Step(action="click", target="#nav-search", fallback_selector="nav a.search"),
            Step(action="fill", target="#query-input", value="{date}",
                 fallback_selector="input[name=q]"),
            Step(action="click", target="#submit", fallback_selector="button[type=submit]"),
            Step(action="wait_for", target="table.results"),
            Step(action="extract", target="table.results tr:first-child"),
        ]

    # relevance set per query = all 5 same-domain variants: any of them is
    # useful context for the task. The metric is COVERAGE — how much of the
    # relevant memory actually fits in the budget. Single-target "is the top
    # hit present" saturates at 1.0 for both strategies; packing is about
    # how much relevant context each token buys.
    relevant: dict[str, set[str]] = {}
    queries: dict[str, str] = {}
    count = 0
    for domain in domains:
        noun = domain.split(".")[0]
        ids = set()
        for variant in variants:
            signature = f"search and export {noun} records {variant}"
            proc = Procedure(
                id=new_id("proc", signature + domain), task_signature=signature,
                domain=domain, steps=_steps(domain), params={"date": "2026-07-01"},
            )
            store.put(proc)
            ids.add(proc.id)
            count += 1
        query = f"pull up the {noun} records around 2026-07-01 and export them"
        queries[query] = domain
        relevant[query] = ids
    print(f"[recall] seeded {count} procedures", flush=True)

    rows = []
    for strategy in ("packed", "topk"):
        for budget in BUDGETS:
            coverage = 0.0
            for query, domain in queries.items():
                packed = recall(store, query, domain=domain, budget=budget,
                                strategy=strategy, kinds=("procedure",))
                found = {i.memory_id for i in packed.items}
                if strategy == "topk":
                    # a naive top-k client still has a context budget: keep
                    # top-ranked full-JSON payloads until it is spent
                    kept, used = set(), 0
                    for item in packed.items:
                        cost = len(item.text) // 4 + 1
                        if used + cost > budget:
                            break
                        used += cost
                        kept.add(item.memory_id)
                    found = kept
                coverage += len(found & relevant[query]) / len(relevant[query])
            rows.append({"strategy": strategy, "budget": budget,
                         "coverage": round(coverage / len(queries), 3)})
            print(f"[recall] {strategy} @{budget}: {rows[-1]['coverage']}", flush=True)
    _write("recall_budget.csv", rows)


def suite_lifecycle() -> None:
    from engram.memory import decay

    born = datetime(2026, 7, 1, tzinfo=timezone.utc)
    last_verified, failures, successes = born, 0, 4
    events = {3.0: "reverified", 6.0: "site changed: replays fail",
              6.5: "relearned → v2", 9.5: "reverified"}
    rows = []
    step = 0.25
    day = 0.0
    while day <= 12:
        now = born + timedelta(days=day)
        event = events.get(day, "")
        if event == "reverified":
            last_verified = now
            successes += 1
        elif event.startswith("site changed"):
            failures += 3
        elif event.startswith("relearned"):
            last_verified, failures, successes = now, 0, 0
        value = decay.freshness(kind="procedure", last_verified=last_verified,
                                failure_count=failures, success_count=successes, now=now)
        rows.append({"day": day, "freshness": round(value, 4), "event": event})
        day = round(day + step, 2)
    _write("lifecycle.csv", rows)


def _write(name: str, rows: list[dict]) -> None:
    path = OUT / name
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[bench] wrote {path} ({len(rows)} rows)")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("recall", "all"):
        suite_recall()
    if which in ("lifecycle", "all"):
        suite_lifecycle()
    if which in ("coldwarm", "all"):
        suite_coldwarm()
