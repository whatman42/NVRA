"""TAHAP 6 — Explicit control-loop state machine. Illegal transitions rejected."""

from __future__ import annotations

from enum import Enum


class ControlState(str, Enum):
    IDLE = "IDLE"
    OBSERVING = "OBSERVING"
    VALIDATING = "VALIDATING"
    ASSESSING = "ASSESSING"
    PREDICTING = "PREDICTING"
    DECIDING = "DECIDING"
    RISK_CHECK = "RISK_CHECK"
    EXECUTION_INTENT = "EXECUTION_INTENT"
    PAPER_EXECUTION = "PAPER_EXECUTION"
    MONITORING = "MONITORING"
    REASSESSMENT = "REASSESSMENT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SAFE_STOP = "SAFE_STOP"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


# Allowed edges (from → frozenset of to)
_ALLOWED: dict[ControlState, frozenset[ControlState]] = {
    ControlState.IDLE: frozenset({ControlState.OBSERVING, ControlState.RECOVERY_REQUIRED}),
    ControlState.OBSERVING: frozenset({ControlState.VALIDATING, ControlState.FAILED, ControlState.SAFE_STOP, ControlState.RECOVERY_REQUIRED}),
    ControlState.VALIDATING: frozenset({ControlState.ASSESSING, ControlState.SAFE_STOP, ControlState.FAILED, ControlState.RECOVERY_REQUIRED}),
    ControlState.ASSESSING: frozenset({ControlState.PREDICTING, ControlState.SAFE_STOP, ControlState.FAILED, ControlState.RECOVERY_REQUIRED}),
    ControlState.PREDICTING: frozenset({ControlState.DECIDING, ControlState.SAFE_STOP, ControlState.FAILED, ControlState.RECOVERY_REQUIRED}),
    ControlState.DECIDING: frozenset({ControlState.RISK_CHECK, ControlState.SAFE_STOP, ControlState.FAILED, ControlState.RECOVERY_REQUIRED}),
    ControlState.RISK_CHECK: frozenset({ControlState.EXECUTION_INTENT, ControlState.SAFE_STOP, ControlState.FAILED, ControlState.RECOVERY_REQUIRED}),
    ControlState.EXECUTION_INTENT: frozenset({ControlState.PAPER_EXECUTION, ControlState.SAFE_STOP, ControlState.FAILED, ControlState.RECOVERY_REQUIRED}),
    ControlState.PAPER_EXECUTION: frozenset({ControlState.MONITORING, ControlState.SAFE_STOP, ControlState.FAILED, ControlState.RECOVERY_REQUIRED}),
    ControlState.MONITORING: frozenset({ControlState.REASSESSMENT, ControlState.COMPLETED, ControlState.SAFE_STOP, ControlState.RECOVERY_REQUIRED}),
    ControlState.REASSESSMENT: frozenset({ControlState.COMPLETED, ControlState.SAFE_STOP, ControlState.FAILED, ControlState.RECOVERY_REQUIRED}),
    ControlState.COMPLETED: frozenset({ControlState.IDLE}),
    ControlState.FAILED: frozenset({ControlState.SAFE_STOP, ControlState.IDLE}),
    ControlState.SAFE_STOP: frozenset({ControlState.IDLE, ControlState.RECOVERY_REQUIRED}),
    ControlState.RECOVERY_REQUIRED: frozenset({ControlState.SAFE_STOP, ControlState.IDLE, ControlState.OBSERVING}),
}


class IllegalTransitionError(ValueError):
    pass


def can_transition(from_state: ControlState, to_state: ControlState) -> bool:
    return to_state in _ALLOWED.get(from_state, frozenset())


def assert_transition(from_state: ControlState, to_state: ControlState) -> None:
    if not can_transition(from_state, to_state):
        raise IllegalTransitionError(f"{from_state.value} → {to_state.value} is not allowed")


TERMINAL_FOR_CYCLE = frozenset(
    {
        ControlState.COMPLETED,
        ControlState.FAILED,
        ControlState.SAFE_STOP,
        ControlState.RECOVERY_REQUIRED,
    }
)
