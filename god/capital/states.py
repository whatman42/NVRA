"""Explicit capital safety transition graph. No magic recovery."""

from __future__ import annotations

from typing import FrozenSet

from .models import CapitalState

ALLOWED_TRANSITIONS: dict[CapitalState, FrozenSet[CapitalState]] = {
    CapitalState.INITIALIZING: frozenset(
        {
            CapitalState.OBSERVING,
            CapitalState.UNKNOWN,
            CapitalState.EMERGENCY_STOP,
        }
    ),
    CapitalState.OBSERVING: frozenset(
        {
            CapitalState.NORMAL,
            CapitalState.CAUTION,
            CapitalState.RESTRICTED,
            CapitalState.PAUSED,
            CapitalState.UNKNOWN,
            CapitalState.EMERGENCY_STOP,
        }
    ),
    CapitalState.NORMAL: frozenset(
        {
            CapitalState.CAUTION,
            CapitalState.RESTRICTED,
            CapitalState.PAUSED,
            CapitalState.EMERGENCY_STOP,
            CapitalState.UNKNOWN,
            CapitalState.OBSERVING,
        }
    ),
    CapitalState.CAUTION: frozenset(
        {
            CapitalState.RESTRICTED,
            CapitalState.PAUSED,
            CapitalState.RECOVERY,
            CapitalState.EMERGENCY_STOP,
            CapitalState.UNKNOWN,
            CapitalState.NORMAL,
        }
    ),
    CapitalState.RESTRICTED: frozenset(
        {
            CapitalState.PAUSED,
            CapitalState.RECOVERY,
            CapitalState.EMERGENCY_STOP,
            CapitalState.UNKNOWN,
            CapitalState.CAUTION,
        }
    ),
    CapitalState.PAUSED: frozenset(
        {
            CapitalState.RECOVERY,
            CapitalState.EMERGENCY_STOP,
            CapitalState.UNKNOWN,
            CapitalState.RESTRICTED,
        }
    ),
    CapitalState.RECOVERY: frozenset(
        {
            CapitalState.NORMAL,
            CapitalState.CAUTION,
            CapitalState.RESTRICTED,
            CapitalState.PAUSED,
            CapitalState.EMERGENCY_STOP,
            CapitalState.UNKNOWN,
            CapitalState.OBSERVING,
        }
    ),
    CapitalState.EMERGENCY_STOP: frozenset(
        {
            CapitalState.RECOVERY,
            CapitalState.UNKNOWN,
            CapitalState.PAUSED,
        }
    ),
    CapitalState.UNKNOWN: frozenset(
        {
            CapitalState.OBSERVING,
            CapitalState.PAUSED,
            CapitalState.EMERGENCY_STOP,
            CapitalState.RECOVERY,
            CapitalState.INITIALIZING,
        }
    ),
}


def can_transition(before: CapitalState, after: CapitalState) -> bool:
    if before == after:
        return True  # idempotent no-op
    return after in ALLOWED_TRANSITIONS.get(before, frozenset())


def assert_transition(before: CapitalState, after: CapitalState) -> None:
    if not can_transition(before, after):
        raise ValueError(
            f"invalid capital safety transition: {before.value} → {after.value}"
        )
