"""decay.py: pure-function freshness math with frozen time."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from engram.memory import decay

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)


def _fresh(days_ago: float, *, kind: str = "procedure", failures: int = 0, successes: int = 0) -> float:
    return decay.freshness(
        kind=kind,
        last_verified=NOW - timedelta(days=days_ago),
        failure_count=failures,
        success_count=successes,
        now=NOW,
    )


def test_new_memory_starts_at_baseline():
    # 0 successes → success factor 0.8, no age decay yet
    assert _fresh(0) == 0.8


def test_procedure_half_life_is_demo_visible():
    half_life = math.log(2) / 0.15  # ≈ 4.62 days
    assert _fresh(half_life, successes=4) == pytest.approx(0.5, rel=1e-6)


def test_preferences_decay_slowly():
    assert _fresh(10, kind="preference", successes=4) > 0.8
    assert _fresh(10, kind="procedure", successes=4) < 0.25


def test_failures_penalize():
    assert _fresh(0, failures=1) == pytest.approx(0.8 * 0.7, rel=1e-6)
    assert _fresh(0, failures=2) < _fresh(0, failures=1)


def test_successes_cap_at_one():
    assert _fresh(0, successes=100) == 1.0


def test_status_thresholds():
    assert decay.status(0.9) == "fresh"
    assert decay.status(0.59) == "stale"
    assert decay.status(0.24) == "invalid"
    assert decay.status(0.9, consecutive_failures=2) == "invalid"
