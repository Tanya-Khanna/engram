"""Guardrails: cycle detection thresholds + JSON parsing."""
from __future__ import annotations

import pytest

from engram.agent import guardrails


def test_cycle_warns_then_aborts():
    detector = guardrails.CycleDetector()
    assert detector.check("http://x/", "click", "#btn") is None
    warning = detector.check("http://x/", "click", "#btn")
    assert warning is not None and "different approach" in warning
    with pytest.raises(guardrails.CycleDetected):
        detector.check("http://x/", "click", "#btn")


def test_cycle_keys_include_url():
    detector = guardrails.CycleDetector()
    assert detector.check("http://x/a", "click", "#btn") is None
    assert detector.check("http://x/b", "click", "#btn") is None  # different page


def test_parse_json_block_tolerates_fences():
    reply = 'Sure!\n```json\n{"action": "click", "target": "#go", "done": false}\n```'
    parsed = guardrails.parse_json_block(reply)
    assert parsed["action"] == "click"


def test_parse_json_block_nested():
    parsed = guardrails.parse_json_block('x {"a": {"b": 1}, "c": [1, 2]} y')
    assert parsed == {"a": {"b": 1}, "c": [1, 2]}


def test_parse_json_block_rejects_junk():
    with pytest.raises(ValueError):
        guardrails.parse_json_block("no json here")
