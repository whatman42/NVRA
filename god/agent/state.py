"""Lifecycle state machine helpers."""

from __future__ import annotations

from typing import FrozenSet, Dict

from .models import LifecycleState
from .errors import InvalidStateError

# Allowed transitions (from → frozenset of allowed next states)
ALLOWED: Dict[LifecycleState, FrozenSet[LifecycleState]] = {
    LifecycleState.CREATED: frozenset({LifecycleState.READY, LifecycleState.STOPPED, LifecycleState.ERROR}),
    LifecycleState.READY: frozenset({
        LifecycleState.OBSERVING,
        LifecycleState.STOPPED,
        LifecycleState.CRASH,
        LifecycleState.ERROR,
    }),
    LifecycleState.OBSERVING: frozenset({
        LifecycleState.DECIDING,
        LifecycleState.READY,  # early abort
        LifecycleState.CRASH,
        LifecycleState.ERROR,
    }),
    LifecycleState.DECIDING: frozenset({
        LifecycleState.EXECUTING,
        LifecycleState.READY,  # NO_ACTION path can short-circuit
        LifecycleState.CRASH,
        LifecycleState.ERROR,
    }),
    LifecycleState.EXECUTING: frozenset({
        LifecycleState.MEASURING,
        LifecycleState.CRASH,
        LifecycleState.ERROR,
    }),
    LifecycleState.MEASURING: frozenset({
        LifecycleState.LEARNING,
        LifecycleState.READY,
        LifecycleState.CRASH,
        LifecycleState.ERROR,
    }),
    LifecycleState.LEARNING: frozenset({
        LifecycleState.READY,
        LifecycleState.CRASH,
        LifecycleState.ERROR,
    }),
    LifecycleState.CRASH: frozenset({
        LifecycleState.RECOVERY,
        LifecycleState.STOPPED,
        LifecycleState.ERROR,
    }),
    LifecycleState.RECOVERY: frozenset({
        LifecycleState.RECONCILIATION,
        LifecycleState.ERROR,
        LifecycleState.STOPPED,
    }),
    LifecycleState.RECONCILIATION: frozenset({
        LifecycleState.READY,
        LifecycleState.ERROR,
        LifecycleState.STOPPED,
    }),
    LifecycleState.STOPPED: frozenset({LifecycleState.CREATED, LifecycleState.READY}),
    LifecycleState.ERROR: frozenset({LifecycleState.RECOVERY, LifecycleState.STOPPED, LifecycleState.CREATED}),
}


def can_transition(current: LifecycleState, target: LifecycleState) -> bool:
    return target in ALLOWED.get(current, frozenset())


def assert_transition(current: LifecycleState, target: LifecycleState) -> None:
    if not can_transition(current, target):
        raise InvalidStateError(f"Cannot transition {current.value} → {target.value}")
