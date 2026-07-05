"""Consolidation: successful Episode trajectory → replayable Procedure.

qwen3.7-max distills the minimal step sequence: dead-ends removed, literals
parameterized, URL shortcuts collapsed to goto+extract when the final URL
encodes the search (the Almanac insight, automated).
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from engram import llm
from engram.agent.guardrails import parse_json_block
from engram.memory.schemas import Episode, Procedure, new_id

_PROMPT = """You turn a browser agent's exploration trajectory into a minimal
replayable procedure. Rules:
- Keep ONLY steps needed to redo the task; drop failed steps and dead ends.
- Parameterize task-specific literals: replace them with {{param}} placeholders
  in step targets/values, and record concrete values in "params".
- URL SHORTCUT: if some URL in the trajectory encodes the search parameters,
  the whole procedure may collapse to one goto (with placeholders in the URL)
  plus one extract.
- For click/fill steps give a "fallback_selector" (a second selector from the
  trajectory's DOM context) when you can.
- "task_signature" is the generalized intent with placeholders, e.g.
  "search flights {{origin}}->{{dest}} {{date}}".

Task: {task}
Domain: {domain}
Trajectory (JSON):
{trajectory}

Reply with strict JSON only:
{{"task_signature": "...", "steps": [{{"action": "goto|click|fill|press|extract|wait_for", "target": "...", "value": null, "fallback_selector": null}}], "params": {{"name": "concrete value used this run"}}, "preconditions": []}}"""


def consolidate(episode: Episode, warm_token_estimate: int = 500) -> Procedure:
    """One deep call, pydantic-validated, one retry with the validation error."""
    trajectory = json.dumps(
        [s for s in episode.trajectory if s.get("ok")], indent=1
    )
    prompt = _PROMPT.format(
        task=episode.task, domain=episode.domain, trajectory=trajectory
    )
    messages = [{"role": "user", "content": prompt}]
    last_error: Exception | None = None
    for _attempt in range(2):
        response = llm.complete("consolidate", messages, model_tier="deep")
        reply = response.choices[0].message.content
        try:
            draft = parse_json_block(reply)
            # id covers the steps too: a relearn after a site change produces a
            # NEW procedure that can supersede the old one, not overwrite it
            return Procedure(
                id=new_id(
                    "proc",
                    f"{draft['task_signature']}{episode.domain}{json.dumps(draft['steps'])}",
                ),
                task_signature=draft["task_signature"],
                domain=episode.domain,
                steps=draft["steps"],
                params=draft.get("params", {}),
                preconditions=draft.get("preconditions", []),
                created_from=episode.id,
                est_cold_tokens=episode.tokens_spent,
                est_warm_tokens=warm_token_estimate,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            last_error = exc
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": reply},
                {
                    "role": "user",
                    "content": f"Your JSON failed validation: {exc}. Reply with corrected strict JSON only.",
                },
            ]
    raise ValueError(f"consolidation failed after retry: {last_error}")
