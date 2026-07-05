"""Warm path: execute a Procedure deterministically — no LLM until the final
one-flash verification. Broken selectors raise ProcedureBroken loudly; silent
fallback would hide staleness from the worker and the Curator.
"""
from __future__ import annotations

import time
from typing import Any

from engram.agent import guardrails
from engram.agent.browser import BrowserSession, act_with_fallback
from engram.memory.schemas import Procedure


class ProcedureBroken(Exception):
    def __init__(self, step_index: int, message: str) -> None:
        self.step_index = step_index
        super().__init__(f"step {step_index}: {message}")


def _substitute(text: str | None, params: dict[str, str]) -> str | None:
    if text is None:
        return None
    for name, value in params.items():
        text = text.replace("{" + name + "}", value)
    return text


def replay(
    procedure: Procedure,
    params: dict[str, str] | None = None,
    task: str | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    """Run the steps; returns {extracted, verified, evidence, seconds}."""
    params = params or procedure.params
    start = time.monotonic()
    extracted: list[str] = []
    with BrowserSession(headless=headless) as browser:
        for i, step in enumerate(procedure.steps):
            target = _substitute(step.target, params) or ""
            value = _substitute(step.value, params)
            fallback = _substitute(step.fallback_selector, params)
            try:
                text, used_fallback = act_with_fallback(
                    browser, step.action, target, value, fallback
                )
            except Exception as exc:  # noqa: BLE001 — surfaces as ProcedureBroken
                raise ProcedureBroken(i, f"{step.action} {target}: {exc}") from exc
            if text:
                extracted.append(text)
            if used_fallback:
                extracted.append(f"[note: step {i} used fallback selector]")

        verdict: dict[str, Any] = {"success": True, "evidence": "no verification task given"}
        if task:
            try:
                verdict = guardrails.done_gate(task, browser.screenshot_b64())
            except Exception as exc:  # noqa: BLE001
                verdict = {"success": False, "evidence": f"verification error: {exc}"}
    if task and not verdict.get("success"):
        raise ProcedureBroken(-1, f"flash verification failed: {verdict.get('evidence')}")
    return {
        "extracted": "\n".join(extracted),
        "verified": bool(verdict.get("success")),
        "evidence": verdict.get("evidence", ""),
        "seconds": round(time.monotonic() - start, 2),
    }
