"""Phase 5F — N.U.N.G. paper execution lifecycle & state integrity. Simulation only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.execution_contract.models import ExecutionIntent, IntentStatus
from god.memory.database import utc_now
from god.research.provenance import content_hash

from .engine import PaperExecutionEngine
from .models import PaperExecution, PaperStatus, build_paper_provenance
from .portfolio import PaperPortfolioEngine, PaperPortfolioState, PortfolioStatus
from .reconciliation import PaperReconciler, ReconciliationStatus
from .risk_models import SafetyDecision
from .safety import PaperSafetyGate


class LifecycleState(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    ACCEPTED = "ACCEPTED"
    SIMULATED = "SIMULATED"
    FILLED = "FILLED"
    RECONCILED = "RECONCILED"
    PORTFOLIO_APPLIED = "PORTFOLIO_APPLIED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    INVALID = "INVALID"
    STALE = "STALE"
    CORRUPTED = "CORRUPTED"
    FAILED = "FAILED"


# Allowed transitions (from → set of to)
_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.CREATED: frozenset(
        {
            LifecycleState.VALIDATED,
            LifecycleState.REJECTED,
            LifecycleState.INVALID,
            LifecycleState.FAILED,
        }
    ),
    LifecycleState.VALIDATED: frozenset(
        {
            LifecycleState.ACCEPTED,
            LifecycleState.REJECTED,
            LifecycleState.INVALID,
            LifecycleState.STALE,
            LifecycleState.FAILED,
        }
    ),
    LifecycleState.ACCEPTED: frozenset(
        {
            LifecycleState.SIMULATED,
            LifecycleState.REJECTED,
            LifecycleState.FAILED,
            LifecycleState.CORRUPTED,
        }
    ),
    LifecycleState.SIMULATED: frozenset(
        {
            LifecycleState.FILLED,
            LifecycleState.REJECTED,
            LifecycleState.FAILED,
            LifecycleState.CORRUPTED,
        }
    ),
    LifecycleState.FILLED: frozenset(
        {
            LifecycleState.RECONCILED,
            LifecycleState.REJECTED,
            LifecycleState.CORRUPTED,
            LifecycleState.FAILED,
        }
    ),
    LifecycleState.RECONCILED: frozenset(
        {
            LifecycleState.PORTFOLIO_APPLIED,
            LifecycleState.REJECTED,
            LifecycleState.CORRUPTED,
            LifecycleState.FAILED,
        }
    ),
    LifecycleState.PORTFOLIO_APPLIED: frozenset(
        {
            LifecycleState.COMPLETED,
            LifecycleState.FAILED,
            LifecycleState.CORRUPTED,
        }
    ),
    LifecycleState.COMPLETED: frozenset(),  # terminal success
    LifecycleState.REJECTED: frozenset(),
    LifecycleState.INVALID: frozenset(),
    LifecycleState.STALE: frozenset(),
    LifecycleState.CORRUPTED: frozenset(),
    LifecycleState.FAILED: frozenset(),
}


def can_transition(current: LifecycleState, target: LifecycleState) -> bool:
    return target in _TRANSITIONS.get(current, frozenset())


SCHEMA_VERSION = "paper-lifecycle-5f-v1"


@dataclass
class LifecycleRecord:
    lifecycle_id: str
    state: LifecycleState
    intent_id: str
    decision_id: str
    cycle_id: str
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    paper_execution_id: Optional[str] = None
    paper_fill_id: Optional[str] = None
    reconciliation_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    reason_codes: tuple[str, ...] = ()
    updated_at: str = ""
    provenance: Optional[dict[str, Any]] = None
    notes: str = "paper_lifecycle_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "lifecycle_id": self.lifecycle_id,
            "state": self.state.value,
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "paper_execution_id": self.paper_execution_id,
            "paper_fill_id": self.paper_fill_id,
            "reconciliation_id": self.reconciliation_id,
            "portfolio_id": self.portfolio_id,
            "reason_codes": list(self.reason_codes),
            "updated_at": self.updated_at,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


def make_lifecycle_id(payload: dict[str, Any]) -> str:
    return "life-" + content_hash(payload)[:24]


class PaperLifecycleEngine:
    """
    Orchestrates paper-only lifecycle:
      CREATED → … → COMPLETED
    Integrates simulation, reconciliation, portfolio, safety gate.
    Never contacts a broker.
    """

    def __init__(
        self,
        *,
        paper_engine: Optional[PaperExecutionEngine] = None,
        portfolio: Optional[PaperPortfolioEngine] = None,
        reconciler: Optional[PaperReconciler] = None,
        safety: Optional[PaperSafetyGate] = None,
        max_records: int = 500,
    ) -> None:
        self.paper_engine = paper_engine or PaperExecutionEngine()
        self.portfolio = portfolio or PaperPortfolioEngine()
        self.reconciler = reconciler or PaperReconciler()
        self.safety = safety or PaperSafetyGate()
        self.max_records = max_records
        self._records: dict[str, LifecycleRecord] = {}
        self._order: list[str] = []

    def run(
        self,
        intent: ExecutionIntent,
        *,
        market_observation: Optional[dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
        data_status: str = "HEALTHY",
        now_iso: Optional[str] = None,
        max_drawdown: Optional[float] = None,
    ) -> LifecycleRecord:
        now = now_iso or utc_now()
        key_payload = {
            "intent_id": intent.intent_id,
            "snapshot_id": snapshot_id or "",
            "schema": SCHEMA_VERSION,
        }
        lid = make_lifecycle_id(key_payload)
        if lid in self._records:
            existing = self._records[lid]
            if existing.state == LifecycleState.COMPLETED:
                return existing  # idempotent

        rec = LifecycleRecord(
            lifecycle_id=lid,
            state=LifecycleState.CREATED,
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            cycle_id=intent.cycle_id,
            content_hash="",
            updated_at=now,
        )
        rec = self._transition(rec, LifecycleState.VALIDATED, now, ("created",))

        # Safety gate
        allowed, assessment = self.safety.allow_paper_progression(
            data_status=data_status,
            decision_status=intent.decision_status,
            decision_id=intent.decision_id,
            cycle_id=intent.cycle_id,
            now_iso=now,
            max_drawdown=max_drawdown,
        )
        if not allowed:
            return self._fail(
                rec,
                LifecycleState.REJECTED,
                now,
                ("safety_blocked", assessment.risk_status.value, *assessment.reason_codes[:5]),
            )

        if intent.intent_status != IntentStatus.VALID:
            return self._fail(
                rec, LifecycleState.INVALID, now, ("intent_not_valid",)
            )

        rec = self._transition(rec, LifecycleState.ACCEPTED, now, ("accepted",))

        # Simulate
        pe = self.paper_engine.simulate(
            intent,
            market_observation=market_observation,
            snapshot_id=snapshot_id,
            now_iso=now,
        )
        if pe.status != PaperStatus.PAPER_SIMULATED or pe.fill is None:
            return self._fail(
                rec,
                LifecycleState.REJECTED,
                now,
                ("simulation_failed", pe.status.value, *pe.reason_codes[:3]),
            )

        rec.paper_execution_id = pe.paper_execution_id
        rec.paper_fill_id = pe.fill.fill_id if pe.fill else None
        rec = self._transition(rec, LifecycleState.SIMULATED, now, ("simulated",))
        rec = self._transition(rec, LifecycleState.FILLED, now, ("filled",))

        # Reconcile
        rrec = self.reconciler.reconcile(pe, intent, now_iso=now)
        rec.reconciliation_id = rrec.record_id
        if rrec.status != ReconciliationStatus.CONSISTENT:
            fail_state = LifecycleState.CORRUPTED
            if rrec.status in (
                ReconciliationStatus.MISSING_INTENT,
                ReconciliationStatus.MISMATCHED_INTENT,
            ):
                fail_state = LifecycleState.REJECTED
            elif rrec.status == ReconciliationStatus.STALE:
                fail_state = LifecycleState.STALE
            return self._fail(
                rec, fail_state, now, ("reconcile_" + rrec.status.value.lower(),)
            )

        rec = self._transition(rec, LifecycleState.RECONCILED, now, ("reconciled",))

        # Portfolio
        pst = self.portfolio.apply(pe, now_iso=now)
        if pst.status == PortfolioStatus.INVALID:
            return self._fail(
                rec, LifecycleState.FAILED, now, ("portfolio_invalid", pst.notes)
            )
        rec.portfolio_id = pst.portfolio_id
        rec = self._transition(
            rec, LifecycleState.PORTFOLIO_APPLIED, now, ("portfolio_applied",)
        )
        rec = self._transition(rec, LifecycleState.COMPLETED, now, ("completed",))
        return self._store(rec)

    def get(self, lifecycle_id: str) -> Optional[LifecycleRecord]:
        return self._records.get(lifecycle_id)

    def _transition(
        self,
        rec: LifecycleRecord,
        target: LifecycleState,
        now: str,
        reasons: tuple[str, ...],
    ) -> LifecycleRecord:
        if not can_transition(rec.state, target):
            return self._fail(
                rec,
                LifecycleState.INVALID,
                now,
                ("invalid_transition", f"{rec.state.value}->{target.value}"),
            )
        payload = {
            "lifecycle_id": rec.lifecycle_id,
            "state": target.value,
            "intent_id": rec.intent_id,
            "decision_id": rec.decision_id,
            "paper_execution_id": rec.paper_execution_id or "",
        }
        rec.state = target
        rec.reason_codes = reasons
        rec.updated_at = now
        rec.content_hash = content_hash(payload)
        rec.provenance = build_paper_provenance(payload)
        return rec

    def _fail(
        self,
        rec: LifecycleRecord,
        state: LifecycleState,
        now: str,
        reasons: tuple[str, ...],
    ) -> LifecycleRecord:
        # terminal failure states always allowed from non-terminal
        payload = {
            "lifecycle_id": rec.lifecycle_id,
            "state": state.value,
            "intent_id": rec.intent_id,
            "reasons": list(reasons),
        }
        rec.state = state
        rec.reason_codes = reasons
        rec.updated_at = now
        rec.content_hash = content_hash(payload)
        rec.provenance = build_paper_provenance(payload)
        rec.notes = "paper_lifecycle_failed"
        return self._store(rec)

    def _store(self, rec: LifecycleRecord) -> LifecycleRecord:
        self._records[rec.lifecycle_id] = rec
        if rec.lifecycle_id not in self._order:
            self._order.append(rec.lifecycle_id)
        while len(self._order) > self.max_records:
            old = self._order.pop(0)
            self._records.pop(old, None)
        return rec
