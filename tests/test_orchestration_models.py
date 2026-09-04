"""Orchestration models restoration — no execution authority."""

from god.orchestration.models import (
    CognitiveStage,
    ContextStatus,
    EventType,
    ResourceClass,
    SchedulerDecision,
    create_context,
    create_event,
    create_task,
    make_checkpoint,
    verify_checkpoint,
)
from god.orchestration.models.context import assert_status_transition
from god.orchestration import EventBus, Scheduler


def test_create_event_deterministic_ids():
    a = create_event(EventType.OBSERVATION, correlation_id="c", context_id="x", sequence=1)
    b = create_event(EventType.OBSERVATION, correlation_id="c", context_id="x", sequence=1)
    assert a.event_id == b.event_id


def test_checkpoint_verify_roundtrip():
    cp = make_checkpoint("ctx1", CognitiveStage.CURIOSITY.value, "OBSERVATION", ["e1", "e2"])
    assert verify_checkpoint(cp)
    cp.content_hash = "deadbeef"
    assert not verify_checkpoint(cp)


def test_status_transitions():
    assert_status_transition(ContextStatus.START, ContextStatus.RUNNING)
    try:
        assert_status_transition(ContextStatus.COMPLETE, ContextStatus.RUNNING)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_scheduler_safety_priority():
    s = Scheduler()
    t = create_task("t1", ResourceClass.SAFETY, priority=1)
    s.enqueue(t)
    decision = s.decide(t)
    assert decision == SchedulerDecision.RUN


def test_eventbus_duplicate_suppression():
    bus = EventBus()
    e = create_event(EventType.RESEARCH, correlation_id="c", context_id="x")
    assert bus.publish(e) is True
    assert bus.publish(e) is True  # idempotent duplicate
    assert bus.pending() == 1
