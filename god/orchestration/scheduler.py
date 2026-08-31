"""Computational scheduler — NEVER trading authorization."""

from __future__ import annotations

from typing import Optional

from .models.task import (
    RESOURCE_PRIORITY,
    MarketPhase,
    OrchTask,
    ResourceClass,
    SchedulerDecision,
)


class Scheduler:
    """Priority: SAFETY > RESEARCH > MAINTENANCE (CPU only)."""

    def __init__(self) -> None:
        self._queue: list[OrchTask] = []

    def enqueue(self, task: OrchTask) -> None:
        self._queue.append(task)
        self._queue.sort(
            key=lambda t: (
                -RESOURCE_PRIORITY.get(t.resource_class, 0),
                -t.priority,
                -t.urgency,
                t.estimated_cost,
            )
        )

    def decide(self, task: OrchTask, *, queue_depth: int = 0, max_depth: int = 100) -> SchedulerDecision:
        if not task.evidence_available and task.resource_class != ResourceClass.SAFETY:
            return SchedulerDecision.DEFER
        if task.dependencies:
            # dependency satisfaction left to caller; mark QUEUE if deps listed
            return SchedulerDecision.QUEUE
        if queue_depth >= max_depth:
            return SchedulerDecision.BLOCK
        if task.market_phase == MarketPhase.CLOSED and task.resource_class == ResourceClass.RESEARCH:
            if task.estimated_cost > 5.0:
                return SchedulerDecision.DEFER
        if task.attempt > 0 and task.attempt >= int(
            task.retry_policy.get("max_attempts", 3)
        ):
            return SchedulerDecision.DROP
        return SchedulerDecision.RUN

    def next_runnable(self, *, queue_depth: int = 0) -> Optional[tuple[OrchTask, SchedulerDecision]]:
        if not self._queue:
            return None
        task = self._queue.pop(0)
        decision = self.decide(task, queue_depth=queue_depth)
        if decision == SchedulerDecision.QUEUE:
            # put back for later
            self._queue.append(task)
        return task, decision

    def pending(self) -> int:
        return len(self._queue)
