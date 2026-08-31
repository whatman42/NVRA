"""Order lifecycle state machine.

Invalid transitions raise TransitionError. No arbitrary state mutation.
"""

from __future__ import annotations

from enum import Enum, auto


class OrderState(Enum):
    PROPOSED = auto()
    RISK_PENDING = auto()
    RISK_APPROVED = auto()
    SUBMITTING = auto()
    SUBMITTED = auto()
    OPEN = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCEL_PENDING = auto()
    CANCELLED = auto()
    REJECTED = auto()
    FAILED = auto()
    UNKNOWN = auto()
    RECONCILING = auto()


class TransitionError(ValueError):
    """Raised when an invalid state transition is attempted."""


# Valid directed edges: from_state -> frozenset of allowed next states
_TRANSITIONS: dict[OrderState, frozenset[OrderState]] = {
    OrderState.PROPOSED: frozenset(
        {OrderState.RISK_PENDING, OrderState.REJECTED, OrderState.FAILED}
    ),
    OrderState.RISK_PENDING: frozenset(
        {OrderState.RISK_APPROVED, OrderState.REJECTED, OrderState.FAILED}
    ),
    OrderState.RISK_APPROVED: frozenset(
        {OrderState.SUBMITTING, OrderState.REJECTED, OrderState.FAILED}
    ),
    OrderState.SUBMITTING: frozenset(
        {
            OrderState.SUBMITTED,
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.REJECTED,
            OrderState.FAILED,
            OrderState.UNKNOWN,
        }
    ),
    OrderState.SUBMITTED: frozenset(
        {
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCEL_PENDING,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.FAILED,
            OrderState.UNKNOWN,
            OrderState.RECONCILING,
        }
    ),
    OrderState.OPEN: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCEL_PENDING,
            OrderState.CANCELLED,
            OrderState.UNKNOWN,
            OrderState.RECONCILING,
        }
    ),
    OrderState.PARTIALLY_FILLED: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCEL_PENDING,
            OrderState.CANCELLED,
            OrderState.UNKNOWN,
            OrderState.RECONCILING,
        }
    ),
    OrderState.CANCEL_PENDING: frozenset(
        {
            OrderState.CANCELLED,
            OrderState.FILLED,  # filled while cancel in flight
            OrderState.PARTIALLY_FILLED,
            OrderState.UNKNOWN,
            OrderState.RECONCILING,
            OrderState.FAILED,
        }
    ),
    OrderState.UNKNOWN: frozenset(
        {
            OrderState.RECONCILING,
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.FAILED,
        }
    ),
    OrderState.RECONCILING: frozenset(
        {
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.FAILED,
            OrderState.UNKNOWN,
            OrderState.SUBMITTED,
        }
    ),
    # Terminal states — no outgoing transitions
    OrderState.FILLED: frozenset(),
    OrderState.CANCELLED: frozenset(),
    OrderState.REJECTED: frozenset(),
    OrderState.FAILED: frozenset(),
}


def can_transition(current: OrderState, target: OrderState) -> bool:
    return target in _TRANSITIONS.get(current, frozenset())


def transition(current: OrderState, target: OrderState) -> OrderState:
    if current is target:
        return current  # identity is always a no-op
    if not can_transition(current, target):
        raise TransitionError(f"invalid transition {current.name} → {target.name}")
    return target


def is_terminal(state: OrderState) -> bool:
    return state in (
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.FAILED,
    )


