"""TAHAP 6/8 — Autonomous control loop."""

from __future__ import annotations

import time

import numpy as np
import pytest

from god.loop import (
    AutonomousControlLoop,
    ControlState,
    ControlCycle,
    can_transition,
    IllegalTransitionError,
)
from god.loop.control_states import assert_transition
from god.market_decision import Quote
from god.market_decision.engine import PositionView


def _quote(seq=1, age=0.0):
    return Quote("EURUSD", time.time() - age, bid=1.1000, ask=1.1002, sequence=seq)


def _closes(n=80, seed=0):
    rng = np.random.default_rng(seed)
    return (100 + np.cumsum(rng.normal(0, 0.2, n))).astype(float).tolist()


def test_valid_and_illegal_transitions():
    assert can_transition(ControlState.IDLE, ControlState.OBSERVING)
    assert not can_transition(ControlState.IDLE, ControlState.PAPER_EXECUTION)
    with pytest.raises(IllegalTransitionError):
        assert_transition(ControlState.IDLE, ControlState.COMPLETED)


def test_cycle_id_and_ttl():
    c = ControlCycle.create("EURUSD", ttl_seconds=1.0, now=100.0)
    assert c.cycle_id.startswith("cyc-")
    assert not c.is_expired(now=100.5)
    assert c.is_expired(now=102.0)


def test_transition_log():
    c = ControlCycle.create("X", now=1.0)
    c.transition(ControlState.OBSERVING, reason="go", now=1.1)
    assert c.transitions[0].from_state == "IDLE"
    assert c.transitions[0].to_state == "OBSERVING"


def test_idempotent_intent_key():
    c = ControlCycle.create("EURUSD", now=1.0)
    k1 = c.intent_key("ENTER")
    k2 = c.intent_key("ENTER")
    assert k1 == k2
    assert c.register_intent(k1) is True
    assert c.register_intent(k1) is False


def test_run_cycle_safe_mode():
    loop = AutonomousControlLoop()
    out = loop.run_cycle(quote=_quote(), closes=_closes(), safe_mode=True)
    assert out.action == "SAFE_STOP"
    assert out.broker_orders_submitted == 0


def test_invalid_quote_safe_stop():
    loop = AutonomousControlLoop()
    q = Quote("EURUSD", time.time(), bid=0.0, ask=1.1)
    out = loop.run_cycle(quote=q, closes=_closes())
    assert out.final_state in ("SAFE_STOP", "FAILED")
    assert out.broker_orders_submitted == 0


def test_position_unknown_safe_stop():
    loop = AutonomousControlLoop()
    out = loop.run_cycle(
        quote=_quote(),
        closes=_closes(),
        position=PositionView(symbol="EURUSD", side="UNKNOWN"),
    )
    assert out.action == "SAFE_STOP"
    assert out.broker_orders_submitted == 0


def test_full_cycle_no_broker(tmp_path):
    loop = AutonomousControlLoop(ml_registry=tmp_path / "ml")
    out = loop.run_cycle(quote=_quote(), closes=_closes(100))
    assert out.broker_orders_submitted == 0
    assert out.to_dict()["broker_orders_submitted"] == 0
    assert out.cycle_id
    assert out.transitions  # has path
    assert out.final_state in ("COMPLETED", "SAFE_STOP")


def test_crash_after_observing_recovery():
    loop = AutonomousControlLoop()
    out = loop.run_cycle(quote=_quote(), closes=_closes(), crash_after_state="OBSERVING")
    assert out.recovery_required is True
    assert out.final_state == "RECOVERY_REQUIRED"
    assert out.broker_orders_submitted == 0


def test_resume_marks_recovery():
    loop = AutonomousControlLoop()
    out1 = loop.run_cycle(quote=_quote(), closes=_closes(), crash_after_state="OBSERVING")
    out2 = loop.run_cycle(quote=_quote(), closes=_closes(), resume_cycle_id=out1.cycle_id)
    assert out2.recovery_required is True
    assert out2.broker_orders_submitted == 0


def test_deterministic_transition_sequence(tmp_path):
    loop = AutonomousControlLoop(ml_registry=tmp_path / "ml2")
    q = _quote()
    c = _closes(90, seed=3)
    a = loop.run_cycle(quote=q, closes=c, now=1_700_000_000.0)
    # second cycle different id but same path shape for no-entry/complete
    b = loop.run_cycle(quote=q, closes=c, now=1_700_000_000.0)
    # states sequence types should match for same inputs (both COMPLETED or both SAFE_STOP)
    assert a.final_state == b.final_state
    assert a.broker_orders_submitted == b.broker_orders_submitted == 0


def test_no_broker_import_in_autonomous():
    from pathlib import Path

    text = Path("god/loop/autonomous.py").read_text(encoding="utf-8")
    for bad in ("order_send", "place_order", "send_order", "MetaTrader5"):
        assert bad not in text
