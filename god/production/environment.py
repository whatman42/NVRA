"""Phase 6A — N.U.N.G. environment separation. Fail-closed."""

from __future__ import annotations

from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


def parse_environment(value: str) -> Environment:
    v = (value or "").strip().lower()
    for env in Environment:
        if env.value == v:
            return env
    raise ValueError(f"unknown_environment:{value!r}")
