"""Operational Control Plane for N.U.N.G. — cognitive decisions only."""

from __future__ import annotations

from typing import Any, Optional

from god.runtime import CognitiveRuntimeRunner, RuntimeOutcome, RuntimeResult, RuntimeStatus

from .audit import CognitiveAuditService
from .commands import ControlCommand
from .correlation import correlate
from .explanations import explain_decision, reasons_from_runtime_notes
from .health import CognitiveHealth, label_for_state
from .ledger import CognitiveDecisionLedger
from .models import (
    ControlCommandType,
    ControlConfig,
    ControlState,
    DecisionStatus,
    LedgerStage,
    VALID_TRANSITIONS,
)


class OperationalController:
    """
    Observes runtime cycles, records ledger, exposes cognitive control commands.
    Does not execute trades.
    """

    def __init__(
        self,
        runner: Optional[CognitiveRuntimeRunner] = None,
        *,
        config: Optional[ControlConfig] = None,
        supervisor: Any = None,
    ) -> None:
        self.runner = runner
        self.supervisor = supervisor
        self.config = config or ControlConfig()
        self.ledger = CognitiveDecisionLedger(self.config)
        self.audit = CognitiveAuditService(self.ledger, self.config)
        self.health = CognitiveHealth()
        self._state = ControlState.STOPPED
        self._cache_invalidated: set[str] = set()
        self._transition(ControlState.READY)

    @property
    def state(self) -> ControlState:
        return self._state

    def _transition(self, target: ControlState) -> bool:
        allowed = VALID_TRANSITIONS.get(self._state, frozenset())
        if target not in allowed and target != self._state:
            if target == ControlState.CORRUPTED:
                self._state = ControlState.CORRUPTED
                self.health.control_state = self._state
                self.health.cognitive_label = label_for_state(self._state)
                self.health.corruption_flag = True
                return True
            return False
        self._state = target
        self.health.control_state = self._state
        self.health.cognitive_label = label_for_state(self._state)
        self.health.pause_requested = self._state == ControlState.PAUSED
        return True

    def dispatch(self, command: ControlCommand) -> dict[str, Any]:
        ct = command.command_type
        if ct == ControlCommandType.STATUS:
            return self.status()
        if ct == ControlCommandType.PAUSE_COGNITIVE_CYCLE:
            ok = self._transition(ControlState.PAUSED)
            return {"ok": ok, "state": self._state.value}
        if ct == ControlCommandType.RESUME_COGNITIVE_CYCLE:
            if self._state == ControlState.CORRUPTED:
                return {"ok": False, "state": self._state.value, "reason": "CORRUPTED"}
            ok = self._transition(ControlState.READY)
            return {"ok": ok, "state": self._state.value}
        if ct == ControlCommandType.REQUEST_HEALTH:
            return self.health.to_dict()
        if ct == ControlCommandType.REQUEST_AUDIT:
            cid = (command.payload or {}).get("cycle_id")
            if not cid:
                return {"ok": False, "reason": "cycle_id_required"}
            return self.audit.audit_cycle(cid)
        if ct == ControlCommandType.INVALIDATE_CYCLE_CACHE:
            cid = (command.payload or {}).get("cycle_id")
            if cid:
                self._cache_invalidated.add(cid)
            return {"ok": True, "invalidated": cid}
        if ct == ControlCommandType.FORCE_REASSESS:
            # Record intent only — actual reassess remains on loop engine if wired
            return {
                "ok": True,
                "command": "FORCE_REASSESS",
                "note": "cognitive_reassess_requested",
            }
        return {"ok": False, "reason": "unknown_command"}

    def status(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "health": self.health.to_dict(),
            "ledger_size": len(self.ledger.recent(10**9)),
        }

    def run_controlled(self, *, force: bool = True) -> Optional[RuntimeResult]:
        """Run one cognitive cycle if control state allows."""
        if self._state in (
            ControlState.PAUSED,
            ControlState.STOPPED,
            ControlState.CORRUPTED,
        ):
            return None
        if self._state == ControlState.UNKNOWN if False else False:
            return None

        if not self._transition(ControlState.RUNNING):
            return None

        result: Optional[RuntimeResult] = None
        try:
            if self.supervisor is not None:
                result = self.supervisor.run_supervised(force=force)
            elif self.runner is not None:
                result = self.runner.run_once(force=force)
            else:
                self._transition(ControlState.READY)
                return None
        except Exception:
            self._transition(ControlState.DEGRADED)
            return None

        self._record_result(result)
        # return to READY or DEGRADED
        if result and result.status in (RuntimeStatus.FAILED, RuntimeStatus.CORRUPTED):
            self._transition(ControlState.DEGRADED)
        elif result and result.outcome == RuntimeOutcome.CORRUPTED:
            self._transition(ControlState.CORRUPTED)
        else:
            self._transition(ControlState.READY)
        return result

    def _record_result(self, result: Optional[RuntimeResult]) -> None:
        if result is None:
            return
        corr = correlate(
            snapshot_id=result.snapshot_id, cycle_id=result.cycle_id
        )
        status = self._map_outcome(result.outcome)
        stage = LedgerStage.COMPLETE
        if result.outcome in (
            RuntimeOutcome.NO_VALID_OPPORTUNITY,
            RuntimeOutcome.NO_VALID_CANDIDATE,
            RuntimeOutcome.INSUFFICIENT_EVIDENCE,
        ):
            stage = LedgerStage.ABSTAIN
        if result.outcome in (RuntimeOutcome.FAILED, RuntimeOutcome.CORRUPTED):
            stage = LedgerStage.FAILED

        codes = reasons_from_runtime_notes(result.notes)
        expl = explain_decision(
            status, reason_codes=codes, config=self.config
        )
        self.ledger.append(
            cycle_id=result.cycle_id or "unknown",
            correlation_id=corr,
            stage=stage,
            status=status,
            snapshot_id=result.snapshot_id,
            discovery_result_id=result.discovery_result_id,
            selection_id=result.selection_id,
            attention_id=result.attention_set_id,
            reason_code=codes[0] if codes else result.outcome.value,
            truncated=bool((result.metadata or {}).get("truncated")),
            notes=result.notes,
            metadata={"explanation_hash": expl.content_hash},
        )
        self.health.last_correlation_id = corr
        self.health.last_snapshot_id = result.snapshot_id
        self.health.current_cycle = result.cycle_id
        self.health.ledger_records = len(self.ledger.recent(10**9))
        if result.outcome in (
            RuntimeOutcome.SUCCESS,
            RuntimeOutcome.NO_VALID_OPPORTUNITY,
            RuntimeOutcome.NO_VALID_CANDIDATE,
            RuntimeOutcome.INSUFFICIENT_EVIDENCE,
        ):
            self.health.last_successful_cycle = result.cycle_id
        else:
            self.health.last_failed_cycle = result.cycle_id

    def _map_outcome(self, outcome: RuntimeOutcome) -> DecisionStatus:
        return {
            RuntimeOutcome.SUCCESS: DecisionStatus.SELECTED,
            RuntimeOutcome.NO_VALID_OPPORTUNITY: DecisionStatus.NO_VALID_OPPORTUNITY,
            RuntimeOutcome.NO_VALID_CANDIDATE: DecisionStatus.NO_VALID_OPPORTUNITY,
            RuntimeOutcome.INSUFFICIENT_EVIDENCE: DecisionStatus.INSUFFICIENT_EVIDENCE,
            RuntimeOutcome.BLOCKED: DecisionStatus.BLOCKED,
            RuntimeOutcome.UNKNOWN: DecisionStatus.UNKNOWN,
            RuntimeOutcome.STALE_DATA: DecisionStatus.DEGRADED,
            RuntimeOutcome.DEGRADED: DecisionStatus.DEGRADED,
            RuntimeOutcome.FAILED: DecisionStatus.FAILED,
            RuntimeOutcome.CORRUPTED: DecisionStatus.FAILED,
            RuntimeOutcome.INVALID_DATA: DecisionStatus.BLOCKED,
            RuntimeOutcome.NO_DATA: DecisionStatus.NO_VALID_OPPORTUNITY,
            RuntimeOutcome.WAITING: DecisionStatus.COMPLETED,
        }.get(outcome, DecisionStatus.UNKNOWN)

    def mark_corrupted(self) -> None:
        self._transition(ControlState.CORRUPTED)
