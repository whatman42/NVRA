"""Persistent lifecycle manager integrated with MemoryStore."""

from __future__ import annotations

from typing import Optional, Any

from god.memory.repositories import MemoryStore
from god.memory.models import AuditRecord
from god.memory.database import utc_now

from .models import LifecycleState
from .state import assert_transition, can_transition
from .errors import InvalidStateError, RecoveryError


STATE_KEY = "agent.lifecycle.state"
LAST_REASON_KEY = "agent.lifecycle.last_reason"
PENDING_REQUEST_KEY = "agent.lifecycle.pending_request_id"


class DefaultLifecycleManager:
    """Owns lifecycle transitions and crash recovery bookkeeping.

    State is persisted via MemoryStore.set_state / get_state so that a
    process restart can detect EXECUTING → CRASH → RECOVERY → RECONCILE.
    """

    def __init__(self, memory: MemoryStore, agent_id: str = "default") -> None:
        self.memory = memory
        self.agent_id = agent_id
        self._component = "lifecycle"

    @property
    def state(self) -> LifecycleState:
        raw = self.memory.get_state(STATE_KEY, LifecycleState.CREATED.value)
        try:
            return LifecycleState(raw)
        except ValueError:
            return LifecycleState.CREATED

    def transition(self, to: LifecycleState, reason: str = "") -> None:
        current = self.state
        assert_transition(current, to)
        old = current.value
        self.memory.set_state(STATE_KEY, to.value)
        self.memory.set_state(LAST_REASON_KEY, reason or "")
        self.memory.append_audit(
            AuditRecord.create(
                component=self._component,
                action="transition",
                entity_type="lifecycle",
                entity_id=self.agent_id,
                old_state={"state": old},
                new_state={"state": to.value},
                reason=reason or f"{old} → {to.value}",
            )
        )

    def force_crash(self, reason: str = "simulated crash") -> None:
        """Test helper / emergency path: move to CRASH regardless of current state."""
        current = self.state
        # Direct write to avoid transition table for true crash simulation
        self.memory.set_state(STATE_KEY, LifecycleState.CRASH.value)
        self.memory.set_state(LAST_REASON_KEY, reason)
        self.memory.append_audit(
            AuditRecord.create(
                component=self._component,
                action="crash",
                entity_type="lifecycle",
                entity_id=self.agent_id,
                old_state={"state": current.value},
                new_state={"state": LifecycleState.CRASH.value},
                reason=reason,
            )
        )

    def set_pending_request(self, request_id: Optional[str]) -> None:
        self.memory.set_state(PENDING_REQUEST_KEY, request_id)

    def get_pending_request(self) -> Optional[str]:
        return self.memory.get_state(PENDING_REQUEST_KEY, None)

    def recover(self) -> None:
        """Drive CRASH → RECOVERY → RECONCILIATION → READY.

        Does not assume any order succeeded; reconciliation is the
        caller's responsibility via ExecutionProvider.reconcile().
        """
        current = self.state
        if current not in (LifecycleState.CRASH, LifecycleState.ERROR, LifecycleState.EXECUTING):
            # If we are already healthy, nothing to do
            if current == LifecycleState.READY:
                return
            # Allow recovery from other terminal-ish states via force
            self.memory.set_state(STATE_KEY, LifecycleState.CRASH.value)

        try:
            if self.state == LifecycleState.CRASH or self.state == LifecycleState.ERROR:
                self.transition(LifecycleState.RECOVERY, reason="start recovery")
            if self.state == LifecycleState.RECOVERY:
                self.transition(LifecycleState.RECONCILIATION, reason="reconcile after recovery")
            if self.state == LifecycleState.RECONCILIATION:
                self.transition(LifecycleState.READY, reason="recovery complete")
                self.set_pending_request(None)
        except InvalidStateError as e:
            raise RecoveryError(str(e)) from e

    def ensure_ready(self) -> None:
        """Idempotent bootstrap: CREATED → READY if needed."""
        if self.state == LifecycleState.CREATED:
            self.transition(LifecycleState.READY, reason="bootstrap")
        elif self.state in (LifecycleState.CRASH, LifecycleState.ERROR, LifecycleState.EXECUTING):
            self.recover()
