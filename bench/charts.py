"""Three charts from bench/out/*.csv → bench/out/*.png (README, video, blog)."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
TEAL, EMBER, GREY = "#0d9488", "#ea580c", "#94a3b8"


def _rows(name: str) -> list[dict[str, str]]:
    with open(OUT / name, newline="") as f:
        return list(csv.DictReader(f))


def chart_cold_vs_warm() -> None:
    rows = _rows("coldwarm.csv")
    tasks = sorted({r["task"] for r in rows})
    cold_t = {r["task"]: float(r["tokens"]) for r in rows if r["path"] == "cold"}
    cold_s = {r["task"]: float(r["seconds"]) for r in rows if r["path"] == "cold"}
    warm_t, warm_s = defaultdict(list), defaultdict(list)
    for r in rows:
        if r["path"] == "warm":
            warm_t[r["task"]].append(float(r["tokens"]))
            warm_s[r["task"]].append(float(r["seconds"]))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    x = range(len(tasks))
    for ax, cold, warm, label in (
        (axes[0], cold_t, warm_t, "tokens"),
        (axes[1], cold_s, warm_s, "seconds"),
    ):
        warm_avg = [sum(warm[t]) / len(warm[t]) if warm[t] else 0 for t in tasks]
        cold_vals = [cold.get(t, 0) for t in tasks]
        ax.bar([i - 0.2 for i in x], cold_vals, 0.4, label="cold (vision loop)", color=EMBER)
        ax.bar([i + 0.2 for i in x], warm_avg, 0.4, label="warm (replay)", color=TEAL)
        ax.set_yscale("log")
        ax.set_xticks(list(x))
        ax.set_xticklabels(tasks, rotation=20, ha="right", fontsize=8)
        ax.set_title(f"{label} per task (log scale)")
        ax.legend()
        for i, (c, w) in enumerate(zip(cold_vals, warm_avg)):
            fmt = (lambda v: f"{v:,.0f}") if label == "tokens" else (lambda v: f"{v:.1f}s")
            ax.annotate(fmt(c), (i - 0.2, c), ha="center", va="bottom", fontsize=7)
            ax.annotate(fmt(w), (i + 0.2, w), ha="center", va="bottom", fontsize=7)
    fig.suptitle("Engram: cold exploration vs warm replay — same tasks")
    fig.tight_layout()
    fig.savefig(OUT / "chart1_cold_vs_warm.png", dpi=160)
    print("chart1_cold_vs_warm.png")


def chart_recall_budget() -> None:
    rows = _rows("recall_budget.csv")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for strategy, color in (("packed", TEAL), ("topk", EMBER)):
        pts = [(int(r["budget"]), float(r["coverage"])) for r in rows if r["strategy"] == strategy]
        pts.sort()
        label = "Engram recall packer" if strategy == "packed" else "naive top-k (full payloads)"
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", color=color, label=label)
        for b, a in pts:
            ax.annotate(f"{a:.0%}", (b, a), textcoords="offset points", xytext=(0, 8), fontsize=8)
    ax.set_xlabel("token budget")
    ax.set_ylabel("relevant-memory coverage in context")
    ax.set_ylim(0, 1.08)
    ax.set_title("Relevant context delivered under budget (35-memory store)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "chart2_recall_budget.png", dpi=160)
    print("chart2_recall_budget.png")


def chart_lifecycle() -> None:
    rows = _rows("lifecycle.csv")
    days = [float(r["day"]) for r in rows]
    fresh = [float(r["freshness"]) for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(days, fresh, color=TEAL, linewidth=2)
    ax.axhline(0.6, color=GREY, linestyle="--", linewidth=1)
    ax.axhline(0.25, color=GREY, linestyle=":", linewidth=1)
    ax.annotate("stale threshold (reverify)", (12, 0.6), fontsize=8, color=GREY,
                va="bottom", ha="right")
    ax.annotate("invalid threshold (relearn)", (12, 0.25), fontsize=8, color=GREY,
                va="bottom", ha="right")
    offsets = [(-10, -28), (-30, 26), (12, 20), (-10, -30)]
    n = 0
    for r in rows:
        if r["event"]:
            d, v = float(r["day"]), float(r["freshness"])
            ax.annotate(r["event"], (d, v), textcoords="offset points",
                        xytext=offsets[n % len(offsets)],
                        fontsize=8, arrowprops={"arrowstyle": "->", "color": EMBER})
            n += 1
    ax.set_xlabel("days")
    ax.set_ylabel("freshness")
    ax.set_ylim(0, 1.12)
    ax.set_title("One procedure's lifecycle: decay → reverify → break → relearn", pad=14)
    fig.tight_layout()
    fig.savefig(OUT / "chart3_freshness_lifecycle.png", dpi=160)
    print("chart3_freshness_lifecycle.png")


if __name__ == "__main__":
    chart_recall_budget()
    chart_lifecycle()
    chart_cold_vs_warm()
