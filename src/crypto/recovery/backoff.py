"""Exponential backoff with jitter."""

from __future__ import annotations

import random


def backoff_seconds(
    base: float,
    attempt: int,
    *,
    max_seconds: float = 300.0,
    jitter_ratio: float = 0.2,
    rng: random.Random | None = None,
) -> float:
    """delay = base * 2^attempt + jitter; capped."""
    exp = min(max_seconds, base * (2 ** max(0, attempt)))
    r = rng or random.Random()
    jitter = exp * jitter_ratio * (r.random() * 2 - 1)
    return float(max(0.0, min(max_seconds, exp + jitter)))
