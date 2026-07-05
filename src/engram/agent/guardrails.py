"""Vision-loop guardrails: cycle detection, done-gate, step budget.

Fallback paths are the product — an episode may fail, but it fails cleanly
and gets stored, because the Curator learns from failures too.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_STEPS = 20

_WARN_AT = 2   # repeats → inject a warning into context
_ABORT_AT = 3  # repeats → abort the episode


class CycleDetected(Exception):
    pass


class CycleDetector:
    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def check(self, url: str, action: str, target: str) -> str | None:
        """Record a step; return a warning to inject, or raise CycleDetected."""
        key = hashlib.sha256(f"{url}|{action}|{target}".encode()).hexdigest()
        count = self._seen[key] = self._seen.get(key, 0) + 1
        if count >= _ABORT_AT:
            raise CycleDetected(f"aborting: {action} {target} repeated {count}x")
        if count >= _WARN_AT:
            return (
                "WARNING: you already tried exactly this action on this page "
                "and it did not finish the task. Try a different approach."
            )
        return None


def done_gate(task: str, final_screenshot_b64: str) -> dict[str, Any]:
    """The model claiming done doesn't count — only flash's verdict does."""
    from engram import llm

    response = llm.complete(
        "done-gate",
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{final_screenshot_b64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Task: {task}\n\nDoes this screenshot show the task"
                            " completed successfully? Answer as strict JSON:"
                            ' {"success": true|false, "evidence": "<one sentence>"}'
                        ),
                    },
                ],
            }
        ],
        model_tier="cheap",
        think=False,
    )
    return parse_json_block(response.choices[0].message.content)


def parse_json_block(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a model reply (tolerates fences)."""
    start = text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in reply: {text[:200]}")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"unterminated JSON object in reply: {text[:200]}")
