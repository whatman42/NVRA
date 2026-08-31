"""Bounded workers — cognitive handlers only. No execution."""

from __future__ import annotations

from typing import Any, Optional

from .bus import EventBus
from .checkpoint_store import CheckpointStore
from .context_store import ContextStore
from .models.checkpoint import make_checkpoint
from .models.context import (
    CognitiveStage,
    ContextStatus,
    assert_status_transition,
)
from .models.events import CognitiveEvent, EventType
from god.memory.database import utc_now


class Worker:
    """Process events through registered handlers; checkpoint after success."""

    def __init__(
        self,
        bus: EventBus,
        context_store: ContextStore,
        checkpoint_store: CheckpointStore,
        handlers: list[Any],
        *,
        poison_threshold: int = 5,
    ) -> None:
        self.bus = bus
        self.contexts = context_store
        self.checkpoints = checkpoint_store
        self.handlers = handlers
        self.poison_threshold = poison_threshold  # infra config, not trading law

    def process_one(self) -> Optional[CognitiveEvent]:
        event = self.bus.consume()
        if event is None:
            return None
        ctx = self.contexts.get(event.context_id)
        if ctx is None:
            self.bus._dead_letter.append(event)
            return event
        if ctx.status in (
            ContextStatus.CORRUPTED,
            ContextStatus.CANCELLED,
            ContextStatus.COMPLETE,
        ):
            return event

        # skip if node already completed (resume)
        node = event.event_type.value
        if node in ctx.completed_nodes and event.event_type not in (
            EventType.POISON,
            EventType.DEAD_LETTER,
        ):
            return event

        try:
            if ctx.status == ContextStatus.START:
                assert_status_transition(ctx.status, ContextStatus.RUNNING)
                ctx.status = ContextStatus.RUNNING
            follow_ons: list[CognitiveEvent] = []
            for h in self.handlers:
                produced = h.handle(event, ctx) or []
                follow_ons.extend(produced)
            # checkpoint
            refs = [event.event_id] + [e.event_id for e in follow_ons]
            cp = make_checkpoint(
                ctx.context_id,
                ctx.current_stage.value,
                node,
                refs,
            )
            self.checkpoints.save(cp)
            ctx.checkpoint_reference = cp.checkpoint_id
            if node not in ctx.completed_nodes:
                ctx.completed_nodes.append(node)
            ctx.attempt_count = 0
            ctx.updated_at = utc_now()
            if ctx.current_stage == CognitiveStage.COMPLETE:
                ctx.status = ContextStatus.COMPLETE
            self.contexts.save(ctx)
            for e in follow_ons:
                self.bus.publish(e)
            return event
        except Exception:
            ctx.attempt_count += 1
            if ctx.attempt_count >= self.poison_threshold:
                ctx.status = ContextStatus.CORRUPTED
                self.contexts.save(ctx)
                from .models.events import create_event

                poison = create_event(
                    EventType.POISON,
                    correlation_id=event.correlation_id,
                    context_id=ctx.context_id,
                    parent_event_id=event.event_id,
                    payload_ref={"reason": "poison_threshold", "attempts": ctx.attempt_count},
                )
                self.bus._dead_letter.append(poison)
            else:
                self.contexts.save(ctx)
            return event

    def drain(self, max_n: int = 100) -> int:
        n = 0
        while n < max_n:
            if self.process_one() is None and self.bus.pending() == 0:
                break
            n += 1
        return n
