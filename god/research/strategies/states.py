"""Lifecycle state machine — explicit, deterministic, auditable transitions.

No automatic promotion based on universal thresholds.
No LIVE / real-execution state.
"""

from __future__ import annotations

from typing import FrozenSet

from .models import LifecycleState

# Allowed directed transitions (from → set of to)
ALLOWED_TRANSITIONS: dict[LifecycleState, FrozenSet[LifecycleState]] = {
    LifecycleState.CANDIDATE: frozenset(
        {
            LifecycleState.EXPERIMENTAL,
            LifecycleState.REJECTED,
            LifecycleState.RETIRED,
        }
    ),
    LifecycleState.EXPERIMENTAL: frozenset(
        {
            LifecycleState.VALIDATING,
            LifecycleState.REJECTED,
            LifecycleState.RETIRED,
            LifecycleState.CANDIDATE,  # rollback / rework
        }
    ),
    LifecycleState.VALIDATING: frozenset(
        {
            LifecycleState.PAPER,
            LifecycleState.REJECTED,
            LifecycleState.DEGRADED,
            LifecycleState.RETIRED,
            LifecycleState.EXPERIMENTAL,  # more experiments needed
        }
    ),
    LifecycleState.PAPER: frozenset(
        {
            LifecycleState.PROBATION,
            LifecycleState.DEGRADED,
            LifecycleState.RETIRED,
            LifecycleState.VALIDATING,
            LifecycleState.PRODUCTION_CANDIDATE,
        }
    ),
    LifecycleState.PROBATION: frozenset(
        {
            LifecycleState.PAPER,
            LifecycleState.DEGRADED,
            LifecycleState.RETIRED,
            LifecycleState.PRODUCTION_CANDIDATE,
            LifecycleState.VALIDATING,
        }
    ),
    LifecycleState.DEGRADED: frozenset(
        {
            LifecycleState.RECOVERY,
            LifecycleState.RETIRED,
            LifecycleState.REJECTED,
        }
    ),
    LifecycleState.RECOVERY: frozenset(
        {
            LifecycleState.VALIDATING,
            LifecycleState.PAPER,
            LifecycleState.PROBATION,
            LifecycleState.DEGRADED,
            LifecycleState.RETIRED,
        }
    ),
    LifecycleState.PRODUCTION_CANDIDATE: frozenset(
        {
            LifecycleState.PAPER,
            LifecycleState.PROBATION,
            LifecycleState.DEGRADED,
            LifecycleState.RETIRED,
            LifecycleState.VALIDATING,
        }
    ),
    LifecycleState.RETIRED: frozenset(),  # terminal (historical knowledge retained)
    LifecycleState.REJECTED: frozenset(
        {
            LifecycleState.CANDIDATE,  # may be revived as new candidate with evidence
            LifecycleState.RETIRED,
        }
    ),
}


def can_transition(from_state: LifecycleState, to_state: LifecycleState) -> bool:
    if from_state == to_state:
        return True  # idempotent no-op
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())


def assert_transition(from_state: LifecycleState, to_state: LifecycleState) -> None:
    if not can_transition(from_state, to_state):
        raise ValueError(
            f"invalid lifecycle transition: {from_state.value} → {to_state.value}"
        )


# States that still have zero capital / execution authority
EXECUTION_LOCKED_STATES = frozenset(LifecycleState)
