"""The Curator's overnight report — what I did while you slept.

/chat surfaces the latest report as its greeting.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engram import metrics
from engram.memory.schemas import Step


def diff_steps(old: list[Step], new: list[Step]) -> list[str]:
    """Readable step diff: what the site change actually changed."""
    def fmt(s: Step) -> str:
        return " ".join(filter(None, (s.action, s.target, s.value)))

    old_set = [fmt(s) for s in old]
    new_set = [fmt(s) for s in new]
    lines = [f"- {line}" for line in old_set if line not in new_set]
    lines += [f"+ {line}" for line in new_set if line not in old_set]
    return lines or ["(steps unchanged)"]


def render_report(sweep: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    verified = [a for a in sweep["reverified"] if "pass" in a["note"]]
    failed_probe = [a for a in sweep["reverified"] if "FAIL" in a["note"]]
    relearned = [a for a in sweep["relearned"] if "new_id" in a]
    lines = [
        f"🌙 Curator run {now} · "
        f"{len(sweep['consolidated'])} consolidated · "
        f"{len(verified)} verified · "
        f"{len(sweep['decayed'])} decayed past a threshold · "
        f"{len(failed_probe)} broken · {len(relearned)} relearned"
    ]
    for action in sweep["consolidated"]:
        lines.append(f"  • consolidated {action['id']} ({action['note']})")
    for action in sweep["decayed"]:
        lines.append(f"  • decay: {action['id']} {action['note']}")
    for action in verified + failed_probe:
        lines.append(f"  • reverify: {action['id']} — {action['note']}")
    for action in relearned:
        lines.append(f"  • relearned {action['id']} → {action['new_id']} ({action['note']}):")
        lines += [f"      {d}" for d in action.get("diff", [])]
        if action.get("savings"):
            lines.append(f"      est. savings preserved: {action['savings']:,} tokens/run")
    for action in sweep["relearned"]:
        if "new_id" not in action:
            lines.append(f"  • relearn attempt {action['id']}: {action['note']}")
    if len(lines) == 1:
        lines.append("  • all memories fresh; nothing to do")
    return "\n".join(lines)


def report_path() -> Path:
    return metrics.data_dir() / "curator_report.md"


def save_report(text: str) -> Path:
    path = report_path()
    path.write_text(text)
    return path


def latest_report() -> str | None:
    path = report_path()
    return path.read_text() if path.exists() else None
