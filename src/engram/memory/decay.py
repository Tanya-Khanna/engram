"""Freshness scoring + invalidation thresholds. Pure functions only.

freshness(m) = exp(-AGE_LAMBDA * days_since(last_verified))
             * (1 - FAIL_PENALTY) ** failure_count
             * min(1, 0.8 + 0.05 * success_count)
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

AGE_LAMBDA: dict[str, float] = {
    "procedure": 0.15,   # ~half-life 4.6 days — demo-visible
    "preference": 0.02,  # people change slowly
    "episode": 0.15,
}
FAIL_PENALTY = 0.3

STALE_THRESHOLD = 0.6      # below → reverify queue
INVALID_THRESHOLD = 0.25   # below (or 2 consecutive failures) → relearn queue
CONSECUTIVE_FAILURE_LIMIT = 2


def days_since(then: datetime, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return max(0.0, (now - then).total_seconds() / 86400)


def freshness(
    *,
    kind: str,
    last_verified: datetime,
    failure_count: int = 0,
    success_count: int = 0,
    now: datetime | None = None,
) -> float:
    age_factor = math.exp(-AGE_LAMBDA[kind] * days_since(last_verified, now))
    fail_factor = (1 - FAIL_PENALTY) ** failure_count
    success_factor = min(1.0, 0.8 + 0.05 * success_count)
    return age_factor * fail_factor * success_factor


def status(freshness_value: float, consecutive_failures: int = 0) -> str:
    """'fresh' | 'stale' (reverify) | 'invalid' (relearn)."""
    if (
        freshness_value < INVALID_THRESHOLD
        or consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT
    ):
        return "invalid"
    if freshness_value < STALE_THRESHOLD:
        return "stale"
    return "fresh"
