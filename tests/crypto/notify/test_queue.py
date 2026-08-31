"""Notification priority, aggregation, rate limit."""

from __future__ import annotations

from crypto.notify import NotifyPriority, NotifyQueue


def test_p0_not_starved() -> None:
    q = NotifyQueue(rate_per_minute=1)
    q.publish("info", "telemetry", priority=NotifyPriority.P3)
    q.publish("EMERGENCY", "stop", priority=NotifyPriority.P0)
    # first pop should be P0 even if P3 was first inserted after sort
    n = q.pop_ready()
    assert n is not None
    assert n.priority is NotifyPriority.P0


def test_aggregation() -> None:
    q = NotifyQueue(aggregate_window_seconds=60.0)

    class C:
        t = 0.0

        def __call__(self) -> float:
            return self.t

    clock = C()
    q._mono = clock
    for _ in range(4):
        clock.t += 1
        q.publish("exchange", "disconnected", priority=NotifyPriority.P2, dedupe_key="ex")
    assert q.pending_count() == 1
    n = q.pop_ready()
    assert n is not None
    assert "unstable" in n.message.lower() or "4" in n.message


def test_secret_redaction() -> None:
    q = NotifyQueue()
    q.publish("x", "api_secret=abc", priority=NotifyPriority.P1)
    n = q.pop_ready()
    assert n is not None
    assert "abc" not in n.message
