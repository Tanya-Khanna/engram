"""Preference extraction (flash) + belief revision on contradiction.

Contradictions keep both statements: the new one links to the old via
`contradicts`, and the old one's confidence drops — beliefs get revised,
not erased.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from engram import llm
from engram.agent.guardrails import parse_json_block
from engram.memory.schemas import Preference, new_id
from engram.memory.store import MemoryStore

_SAME_TOPIC = 60  # fuzz score: same subject, possibly different stance
_PROMPT = """Extract durable user preferences from this conversation.
Only include stable tastes/constraints (seating, budgets, airlines, formats),
not one-off task details. Quote the exact evidence.

Conversation:
{transcript}

Reply with strict JSON only: {{"preferences": [{{"statement": "prefers ...", "evidence": "<exact quote>"}}]}}"""


def extract_preferences(transcript: str, store: MemoryStore) -> list[Preference]:
    response = llm.complete(
        "preference-extraction",
        [{"role": "user", "content": _PROMPT.format(transcript=transcript)}],
        model_tier="cheap",
        think=False,
    )
    parsed = parse_json_block(response.choices[0].message.content)
    stored: list[Preference] = []
    for item in parsed.get("preferences", []):
        preference = Preference(
            id=new_id("pref", item["statement"]),
            statement=item["statement"],
            evidence=[item.get("evidence", "")],
        )
        _revise_beliefs(store, preference)
        store.put(preference)
        stored.append(preference)
    return stored


def _revise_beliefs(store: MemoryStore, new: Preference) -> None:
    for row in store.list(kind="preference"):
        if row["id"] == new.id:
            continue
        old = store.get(row["id"])
        if not isinstance(old, Preference):
            continue
        score = fuzz.token_set_ratio(new.statement, old.statement)
        if score >= _SAME_TOPIC and new.statement != old.statement:
            new.contradicts = old.id
            old.confidence = round(old.confidence * 0.6, 3)
            store.put(old)
