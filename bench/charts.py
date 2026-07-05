"""Three charts from bench/out/*.csv → bench/out/*.png (README, landing, video).

Plotly, styled to the terminal-brutalist design system: mono type, cream
paper, ink lines, one accent. No gradients, no rounded anything.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import plotly.graph_objects as go

OUT = Path(__file__).resolve().parent / "out"

PAPER = "#f2efe6"
INK = "#141414"
DIM = "#6b6b66"
ACCENT = "#d84a05"
MONO = "Menlo, DejaVu Sans Mono, Courier New, monospace"


def _rows(name: str) -> list[dict[str, str]]:
    with open(OUT / name, newline="") as f:
        return list(csv.DictReader(f))


def _layout(title: str, **kw) -> dict:
    base = {
        "title": {"text": title.upper(), "font": {"size": 14}, "x": 0.02,
                  "y": 0.97, "yanchor": "top"},
        "font": {"family": MONO, "color": INK, "size": 12},
        "paper_bgcolor": PAPER,
        "plot_bgcolor": PAPER,
        "margin": {"l": 70, "r": 30, "t": 110, "b": 60},
        "xaxis": {"linecolor": INK, "linewidth": 2, "gridcolor": "#dcd8cb",
                  "zeroline": False, "mirror": True},
        "yaxis": {"linecolor": INK, "linewidth": 2, "gridcolor": "#dcd8cb",
                  "zeroline": False, "mirror": True},
        "legend": {"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0,
                   "bgcolor": "rgba(0,0,0,0)"},
    }
    base.update(kw)
    return base


def _export(fig: go.Figure, name: str, width: int, height: int) -> None:
    fig.write_image(str(OUT / name), width=width, height=height, scale=2)
    print(name)


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

    for metric, cold, warm, suffix, name in (
        ("tokens", cold_t, warm_t, "", "chart1_cold_vs_warm.png"),
        ("seconds", cold_s, warm_s, "s", "chart1b_cold_vs_warm_seconds.png"),
    ):
        warm_avg = [sum(warm[t]) / len(warm[t]) if warm[t] else 0 for t in tasks]
        cold_vals = [cold.get(t, 0) for t in tasks]
        fmt = (lambda v: f"{v:,.0f}") if metric == "tokens" else (lambda v: f"{v:.1f}s")
        fig = go.Figure(
            [
                go.Bar(name="cold (vision loop)", x=tasks, y=cold_vals,
                       marker={"color": INK},
                       text=[fmt(v) for v in cold_vals], textposition="outside"),
                go.Bar(name="warm (replay)", x=tasks, y=warm_avg,
                       marker={"color": ACCENT},
                       text=[fmt(v) for v in warm_avg], textposition="outside"),
            ]
        )
        fig.update_layout(
            _layout(f"cold vs warm: {metric} per task (log scale)"),
            barmode="group", bargap=0.35,
        )
        fig.update_yaxes(type="log")
        fig.update_traces(textfont={"family": MONO, "size": 11})
        _export(fig, name, 1000, 480)


def chart_recall_budget() -> None:
    rows = _rows("recall_budget.csv")
    fig = go.Figure()
    # topk first so the packer's accent line draws on top where they overlap
    for strategy, color, label in (
        ("topk", DIM, "naive top-k (full payloads)"),
        ("packed", ACCENT, "engram recall packer"),
    ):
        pts = sorted(
            (int(r["budget"]), float(r["coverage"]))
            for r in rows if r["strategy"] == strategy
        )
        fig.add_trace(
            go.Scatter(
                x=[p[0] for p in pts], y=[p[1] for p in pts],
                name=label, mode="lines+markers+text",
                line={"color": color, "width": 3},
                marker={"size": 10, "symbol": "square", "color": color},
                text=[f"{p[1]:.0%}" for p in pts], textposition="top center",
                textfont={"family": MONO, "size": 11, "color": color},
            )
        )
    fig.update_layout(_layout("relevant context delivered under budget"))
    fig.update_xaxes(title="token budget", tickvals=[500, 1500, 4000])
    fig.update_yaxes(title="coverage", range=[0, 1.12], tickformat=".0%")
    _export(fig, "chart2_recall_budget.png", 900, 500)


def chart_lifecycle() -> None:
    rows = _rows("lifecycle.csv")
    days = [float(r["day"]) for r in rows]
    fresh = [float(r["freshness"]) for r in rows]
    fig = go.Figure(
        go.Scatter(x=days, y=fresh, mode="lines", showlegend=False,
                   line={"color": INK, "width": 3})
    )
    for y, dash, label in (
        (0.6, "dash", "stale threshold (reverify)"),
        (0.25, "dot", "invalid threshold (relearn)"),
    ):
        fig.add_hline(y=y, line={"color": DIM, "width": 1, "dash": dash})
        fig.add_annotation(x=12, y=y, text=label, showarrow=False,
                           font={"color": DIM, "size": 11},
                           xanchor="right", yanchor="bottom")
    shifts = {"reverified": (-30, -34), "site changed: replays fail": (0, 44),
              "relearned → v2": (40, -30)}
    for r in rows:
        if r["event"]:
            dx, dy = shifts.get(r["event"], (0, -40))
            fig.add_annotation(
                x=float(r["day"]), y=float(r["freshness"]), text=r["event"],
                ax=dx, ay=dy, arrowcolor=ACCENT, arrowwidth=1.5,
                font={"size": 11, "color": INK},
            )
    fig.update_layout(
        _layout("one procedure's lifecycle: decay, reverify, break, relearn")
    )
    fig.update_xaxes(title="days")
    fig.update_yaxes(title="freshness", range=[0, 1.12])
    _export(fig, "chart3_freshness_lifecycle.png", 1100, 480)


if __name__ == "__main__":
    chart_recall_budget()
    chart_lifecycle()
    chart_cold_vs_warm()
