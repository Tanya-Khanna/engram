"""Cold path: screenshot → plan → act → verify, on qwen3.7-plus.

Slow and expensive by design — it runs once per task, then consolidation
turns the trajectory into a replayable Procedure.
"""
from __future__ import annotations

import logging
from typing import Any

from engram import llm, metrics
from engram.agent import guardrails
from engram.agent.browser import BrowserSession
from engram.memory.schemas import Episode, new_id

logger = logging.getLogger(__name__)

_SYSTEM = """You control a web browser to complete a task. Each turn you get:
the task, the current URL, a screenshot, a DOM snapshot of interactive
elements with their CSS selectors, and the actions taken so far.

Reply with ONE action as strict JSON, nothing else:
{"action": "goto|click|fill|press|extract|wait_for", "target": "<url, CSS selector from the DOM snapshot, or key>", "value": "<fill text, else null>", "reasoning": "<one sentence>", "done": false}

Rules:
- Prefer selectors that appear in the DOM snapshot. Never invent selectors.
- If the page already shows the information the task asks for, use
  {"action": "extract", "target": "<selector of the element with the answer>", "done": true}.
- Set done=true only when the task is fully complete."""


def run_episode(
    task: str,
    start_url: str,
    session_id: str = "cold",
    headless: bool = True,
    max_steps: int = guardrails.MAX_STEPS,
    extra_context: str | None = None,
) -> Episode:
    """Explore a task with vision; always returns a stored-shape Episode."""
    episode = Episode(
        id=new_id("ep", f"{task}{start_url}{session_id}"),
        session_id=session_id,
        task=task,
        domain=_domain(start_url),
        outcome="aborted",
    )
    shots_dir = metrics.data_dir() / "screenshots" / episode.id
    shots_dir.mkdir(parents=True, exist_ok=True)
    episode.screenshots_dir = str(shots_dir)
    tokens = 0
    cycles = guardrails.CycleDetector()
    warning: str | None = None

    with BrowserSession(headless=headless) as browser:
        browser.act("goto", start_url)
        episode.trajectory.append(
            {"action": "goto", "target": start_url, "value": None, "ok": True}
        )
        for step_no in range(max_steps):
            screenshot = browser.screenshot_b64()
            browser.screenshot_save(str(shots_dir / f"step_{step_no}.jpg"))
            response = llm.complete(
                "vision-loop",
                _messages(task, browser, screenshot, episode.trajectory, warning, extra_context),
                model_tier="vision",
            )
            tokens += response.usage.total_tokens
            warning = None
            try:
                move = guardrails.parse_json_block(response.choices[0].message.content)
            except ValueError as exc:
                logger.warning("unparseable action (%s); asking again", exc)
                warning = "Your last reply was not valid JSON. Reply with one JSON action only."
                continue

            record: dict[str, Any] = {
                "action": move.get("action"),
                "target": move.get("target", ""),
                "value": move.get("value"),
                "reasoning": move.get("reasoning", ""),
                "url": browser.url,
            }
            try:
                warning = cycles.check(browser.url, record["action"], record["target"])
                extracted = browser.act(record["action"], record["target"], record["value"])
                record["ok"] = True
                if extracted:
                    record["extracted"] = extracted[:2000]
            except guardrails.CycleDetected as exc:
                record.update(ok=False, error=str(exc))
                episode.trajectory.append(record)
                episode.outcome = "aborted"
                episode.summary = f"aborted: {exc}"
                break
            except Exception as exc:  # noqa: BLE001 — recorded, model retries
                record.update(ok=False, error=str(exc)[:200])
                warning = f"That action failed: {str(exc)[:200]}. Try something else."
            episode.trajectory.append(record)

            if move.get("done") and record["ok"]:
                verdict = done_verdict(task, browser)
                tokens += verdict.pop("_tokens", 0)
                episode.summary = str(verdict.get("evidence", ""))
                if verdict.get("success"):
                    episode.outcome = "success"
                else:
                    warning = (
                        "A verifier checked your claim of completion and rejected it:"
                        f" {verdict.get('evidence')}. Keep going."
                    )
                    episode.outcome = "failure"
                    continue
                break
        else:
            episode.outcome = "failure"
            episode.summary = f"step budget ({max_steps}) exhausted"

    episode.tokens_spent = tokens
    return episode


def done_verdict(task: str, browser: BrowserSession) -> dict[str, Any]:
    try:
        return guardrails.done_gate(task, browser.screenshot_b64())
    except Exception as exc:  # noqa: BLE001 — verifier failure = not verified
        return {"success": False, "evidence": f"done-gate error: {exc}"}


def _messages(
    task: str,
    browser: BrowserSession,
    screenshot_b64: str,
    trajectory: list[dict[str, Any]],
    warning: str | None,
    extra_context: str | None = None,
) -> list[dict[str, Any]]:
    history = "\n".join(
        f"{i}. {s['action']} {s['target']}"
        + (f" = '{s['value']}'" if s.get("value") else "")
        + ("" if s.get("ok") else f"  FAILED: {s.get('error', '?')}")
        for i, s in enumerate(trajectory, 1)
    )
    text = (
        f"Task: {task}\nCurrent URL: {browser.url}\n\nActions so far:\n{history}\n\n"
        f"DOM snapshot:\n{browser.dom_snapshot()}"
    )
    if extra_context:
        text = f"{extra_context}\n\n{text}"
    if warning:
        text += f"\n\n{warning}"
    return [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"},
                },
                {"type": "text", "text": text},
            ],
        },
    ]


def _domain(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0]
