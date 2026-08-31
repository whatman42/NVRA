"""TAHAP 6 — Cycle identity, transition log, audit trail, idempotency keys."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from .control_states import ControlState, assert_transition, can_transition, TERMINAL_FOR_CYCLE


@dataclass(frozen=True)
class TransitionRecord:
    cycle_id: str
    from_state: str
    to_state: str
    timestamp: float
    reason: str
    evidence_ids: tuple[str, ...] = ()
    status: str = "OK"
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "status": self.status,
            "failure_code": self.failure_code,
            "failure_reason": self.failure_reason,
        }


@dataclass
class ControlCycle:
    cycle_id: str
    symbol: str
    created_at: float
    expires_at: float
    state: ControlState = ControlState.IDLE
    transitions: list[TransitionRecord] = field(default_factory=list)
    intent_ids: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    failure_code: Optional[str] = None
    broker_orders_submitted: int = 0

    @staticmethod
    def create(symbol: str, *, ttl_seconds: float = 120.0, now: Optional[float] = None) -> "ControlCycle":
        now = now if now is not None else time.time()
        cid = "cyc-" + uuid.uuid4().hex[:16]
        return ControlCycle(
            cycle_id=cid,
            symbol=symbol,
            created_at=now,
            expires_at=now + ttl_seconds,
            state=ControlState.IDLE,
        )

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return now > self.expires_at

    def transition(
        self,
        to_state: ControlState,
        *,
        reason: str,
        evidence_ids: tuple[str, ...] = (),
        failure_code: Optional[str] = None,
        failure_reason: Optional[str] = None,
        now: Optional[float] = None,
        force_validate: bool = True,
    ) -> TransitionRecord:
        now = now if now is not None else time.time()
        if force_validate:
            assert_transition(self.state, to_state)
        status = "OK" if failure_code is None else "FAILURE"
        rec = TransitionRecord(
            cycle_id=self.cycle_id,
            from_state=self.state.value,
            to_state=to_state.value,
            timestamp=now,
            reason=reason,
            evidence_ids=evidence_ids,
            status=status,
            failure_code=failure_code,
            failure_reason=failure_reason,
        )
        self.state = to_state
        self.transitions.append(rec)
        if failure_code:
            self.failure_code = failure_code
        return rec

    def register_intent(self, intent_id: str) -> bool:
        """Idempotent: return False if intent already registered for this cycle."""
        if intent_id in self.intent_ids:
            return False
        self.intent_ids.append(intent_id)
        return True

    def intent_key(self, decision_action: str) -> str:
        raw = f"{self.cycle_id}:{decision_action}:{self.symbol}"
        return "intent-" + hashlib.sha256(raw.encode()).hexdigest()[:20]

    def to_audit(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "symbol": self.symbol,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "state": self.state.value,
            "transitions": [t.to_dict() for t in self.transitions],
            "intent_ids": list(self.intent_ids),
            "audit": dict(self.audit),
            "failure_code": self.failure_code,
            "broker_orders_submitted": 0,
            "terminal": self.state in TERMINAL_FOR_CYCLE,
        }
