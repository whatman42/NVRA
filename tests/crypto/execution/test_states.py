"""State machine transitions."""

from __future__ import annotations

import pytest

from crypto.execution.states import OrderState, TransitionError, can_transition, transition


def test_valid_happy_path() -> None:
    s = OrderState.PROPOSED
    s = transition(s, OrderState.RISK_PENDING)
    s = transition(s, OrderState.RISK_APPROVED)
    s = transition(s, OrderState.SUBMITTING)
    s = transition(s, OrderState.OPEN)
    s = transition(s, OrderState.FILLED)
    assert s is OrderState.FILLED


def test_invalid_transition() -> None:
    with pytest.raises(TransitionError):
        transition(OrderState.FILLED, OrderState.OPEN)


def test_unknown_to_reconcile() -> None:
    assert can_transition(OrderState.UNKNOWN, OrderState.RECONCILING)
    assert transition(OrderState.UNKNOWN, OrderState.RECONCILING) is OrderState.RECONCILING


def test_terminal_no_exit() -> None:
    assert not can_transition(OrderState.CANCELLED, OrderState.OPEN)
    assert not can_transition(OrderState.REJECTED, OrderState.SUBMITTING)
