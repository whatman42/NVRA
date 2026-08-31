"""TAHAP 6 — Autonomous Control Loop orchestrator.

Wires: observe → validate → assess → ML → market_decision → risk → execution_contract (paper/null).
LIVE CAPITAL BLOCKED. broker_orders_submitted always 0.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from god.market_decision import Quote, MarketDecisionEngine, validate_quote
from god.market_decision.engine import PositionView
from god.market_decision.stream_health import StreamHealthMonitor
from god.ml import MLPipeline, MLEvidence
from god.ml.prediction import PredictionStatus
from god.execution_contract.engine import ExecutionContractEngine
from god.loop.evidence_fusion import fuse_evidence
from god.loop.models import EvidenceContext
from god.loop.control_states import ControlState, IllegalTransitionError
from god.loop.control_cycle import ControlCycle
from god.institutional import InstitutionalKernel, KernelConfig
from god.institutional.contracts import DecisionPacket


@dataclass
class CycleOutcome:
    cycle_id: str
    final_state: str
    action: str
    reasons: list[str] = field(default_factory=list)
    transitions: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    broker_orders_submitted: int = 0
    intent_id: Optional[str] = None
    recovery_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "final_state": self.final_state,
            "action": self.action,
            "reasons": list(self.reasons),
            "transitions": list(self.transitions),
            "audit": dict(self.audit),
            "broker_orders_submitted": 0,
            "intent_id": self.intent_id,
            "recovery_required": self.recovery_required,
        }


class AutonomousControlLoop:
    """
    Deterministic, fail-closed cycle runner.
    Does not call broker adapters for live orders.
    """

    def __init__(
        self,
        *,
        ml_registry: Optional[Path] = None,
        decision_engine: Optional[MarketDecisionEngine] = None,
        stream: Optional[StreamHealthMonitor] = None,
        cycle_ttl_seconds: float = 120.0,
        max_retries: int = 2,
        stage_timeout_seconds: float = 30.0,
    ) -> None:
        self.decision = decision_engine or MarketDecisionEngine(stream=stream)
        self.stream = stream or self.decision.stream
        self.ml_registry = ml_registry or Path("/tmp/nung_ml_reg")
        self._ml: Optional[MLPipeline] = None
        self.cycle_ttl_seconds = cycle_ttl_seconds
        self.max_retries = max_retries
        self.stage_timeout_seconds = stage_timeout_seconds
        self._cycles: dict[str, ControlCycle] = {}
        self._intent_registry: set[str] = set()  # global idempotency
        self._exec = ExecutionContractEngine()
        # Institutional kernel is the orchestration/audit spine; the existing
        # control cycle remains the execution authority. The kernel executor is
        # intentionally observational to prevent double execution.
        self._institutional = InstitutionalKernel(
            KernelConfig(state_dir=str(self.ml_registry.parent / "institutional_state")),
            executor=lambda d: {"status": "OBSERVATION_ONLY", "action": d.action, "symbol": d.symbol},
        )

    def _ml_pipe(self) -> MLPipeline:
        if self._ml is None:
            self._ml = MLPipeline(self.ml_registry)
        return self._ml

    def _safe_stop(self, cycle: ControlCycle, reason: str, code: str) -> CycleOutcome:
        try:
            if cycle.state not in (ControlState.SAFE_STOP, ControlState.FAILED, ControlState.COMPLETED):
                # prefer SAFE_STOP if allowed, else FAILED then SAFE_STOP
                if cycle.state != ControlState.FAILED:
                    try:
                        cycle.transition(ControlState.SAFE_STOP, reason=reason, failure_code=code, failure_reason=reason)
                    except IllegalTransitionError:
                        try:
                            cycle.transition(ControlState.FAILED, reason=reason, failure_code=code, failure_reason=reason)
                            cycle.transition(ControlState.SAFE_STOP, reason="after_fail", failure_code=code)
                        except IllegalTransitionError:
                            pass
        except Exception:
            pass
        return CycleOutcome(
            cycle_id=cycle.cycle_id,
            final_state=cycle.state.value,
            action="SAFE_STOP",
            reasons=[reason, code],
            transitions=[f"{t.from_state}->{t.to_state}" for t in cycle.transitions],
            audit=cycle.to_audit(),
            broker_orders_submitted=0,
        )

    def run_cycle(
        self,
        *,
        quote: Quote,
        closes: Sequence[float] | None = None,
        position: Optional[PositionView] = None,
        symbol: Optional[str] = None,
        now: Optional[float] = None,
        crash_after_state: Optional[str] = None,
        resume_cycle_id: Optional[str] = None,
        reconciliation_healthy: bool = True,
        safe_mode: bool = False,
    ) -> CycleOutcome:
        now = now if now is not None else time.time()
        symbol = symbol or quote.symbol

        # Recovery path
        if resume_cycle_id and resume_cycle_id in self._cycles:
            cycle = self._cycles[resume_cycle_id]
            if cycle.state not in (ControlState.COMPLETED, ControlState.IDLE):
                if cycle.state != ControlState.RECOVERY_REQUIRED:
                    cycle.transition(ControlState.RECOVERY_REQUIRED, reason="restart", force_validate=True)
                return CycleOutcome(
                    cycle_id=cycle.cycle_id,
                    final_state=cycle.state.value,
                    action="RECOVERY_REQUIRED",
                    reasons=["process_restart"],
                    transitions=[f"{t.from_state}->{t.to_state}" for t in cycle.transitions],
                    audit=cycle.to_audit(),
                    recovery_required=True,
                    broker_orders_submitted=0,
                )

        cycle = ControlCycle.create(symbol, ttl_seconds=self.cycle_ttl_seconds, now=now)
        self._cycles[cycle.cycle_id] = cycle

        if safe_mode:
            cycle.transition(ControlState.OBSERVING, reason="start")
            return self._safe_stop(cycle, "SAFE_MODE", "SAFE_MODE")

        # OBSERVING
        cycle.transition(ControlState.OBSERVING, reason="start_observe")
        if crash_after_state == "OBSERVING":
            cycle.transition(ControlState.RECOVERY_REQUIRED, reason="simulated_crash")
            return CycleOutcome(
                cycle_id=cycle.cycle_id,
                final_state=cycle.state.value,
                action="RECOVERY_REQUIRED",
                reasons=["crash_after_OBSERVING"],
                transitions=[f"{t.from_state}->{t.to_state}" for t in cycle.transitions],
                audit=cycle.to_audit(),
                recovery_required=True,
            )

        # VALIDATING
        cycle.transition(ControlState.VALIDATING, reason="validate_quote")
        self.stream.on_message(sequence=getattr(quote, "sequence", None) or 1, ts=quote.timestamp)
        qv = validate_quote(quote, now=now)
        if not qv.ok:
            return self._safe_stop(cycle, "quote_invalid:" + ",".join(qv.reasons), "DATA_FAILURE")
        sh = self.stream.tick(now=now)
        if not sh.allows_new_entry:
            return self._safe_stop(cycle, f"stream:{sh.state.value}", "STREAM_FAILURE")
        if not reconciliation_healthy:
            return self._safe_stop(cycle, "reconciliation_unhealthy", "DATA_FAILURE")
        if position is not None and position.side == "UNKNOWN":
            return self._safe_stop(cycle, "position_unknown", "UNKNOWN_FAILURE")
        if position is not None and position.recovery_incomplete:
            return self._safe_stop(cycle, "position_recovery_incomplete", "UNKNOWN_FAILURE")
        if cycle.is_expired(now):
            return self._safe_stop(cycle, "cycle_ttl_expired", "TIMEOUT")

        # ASSESSING — evidence fusion (existing)
        cycle.transition(ControlState.ASSESSING, reason="fuse_evidence")
        evidence_ctx = EvidenceContext(
            uncertainty="LOW",
            evidence_refs=[f"quote:{symbol}", f"stream:{sh.state.value}"],
            notes="tahap6_observe",
        )
        # fuse_evidence may need richer inputs — call safely
        try:
            fused = fuse_evidence(instrument=symbol)
            if hasattr(fused, "uncertainty") and fused.uncertainty:
                evidence_ctx.uncertainty = fused.uncertainty
            if hasattr(fused, "evidence_refs") and fused.evidence_refs:
                evidence_ctx.evidence_refs = list(fused.evidence_refs) + evidence_ctx.evidence_refs
        except Exception:
            # keep local evidence_ctx — fusion optional enrichment
            cycle.audit["fusion"] = "fallback_local"

        # PREDICTING — TAHAP 5 ML
        cycle.transition(ControlState.PREDICTING, reason="ml_predict")
        ml_evidence: Optional[MLEvidence] = None
        closes = list(closes) if closes is not None else []
        try:
            if len(closes) >= 40:
                pipe = self._ml_pipe()
                ml_out = pipe.run(closes, symbol=symbol, regime="TRENDING", use_calibration_split=False)
                ml_evidence = ml_out.evidence
                cycle.audit["ml"] = ml_out.prediction.to_dict() if ml_out.prediction else None
                if ml_out.prediction and ml_out.prediction.status not in (
                    PredictionStatus.VALID,
                    PredictionStatus.BLOCKED,
                ):
                    if ml_out.prediction.status in (
                        PredictionStatus.MODEL_UNAVAILABLE,
                        PredictionStatus.CALIBRATION_INVALID,
                        PredictionStatus.OUT_OF_DISTRIBUTION,
                        PredictionStatus.INSUFFICIENT_DATA,
                    ):
                        # still continue to decision — decision may NO_TRADE
                        cycle.audit["ml_status"] = ml_out.prediction.status.value
            else:
                cycle.audit["ml"] = "skipped_insufficient_history"
        except Exception as e:
            return self._safe_stop(cycle, f"model_failure:{e}", "MODEL_FAILURE")

        # DECIDING — TAHAP 4
        cycle.transition(ControlState.DECIDING, reason="market_decision")
        try:
            decision = self.decision.run(
                quote=quote,
                closes=closes if closes else None,
                position=position,
                now=now,
                reconciliation_healthy=reconciliation_healthy,
                ml_evidence=ml_evidence,
            )
            cycle.audit["decision"] = decision.to_dict()
            # Publish a typed decision snapshot through the institutional kernel.
            # This adds deterministic event/checkpoint semantics without creating
            # a second execution path.
            packet = DecisionPacket(
                symbol=symbol,
                action=("BUY" if decision.action == "BUY" else "SELL" if decision.action == "SELL" else "HOLD"),
                confidence=float(getattr(decision, "confidence", 0.0) or 0.0),
                thesis="market_decision_engine",
                risks=tuple(getattr(decision, "reasons", ()) or ()),
                suggested_size=0.0,
                correlation_id=cycle.cycle_id,
            )
            self._institutional.submit_decision(packet)
            self._institutional.drain()
            cycle.audit["institutional_kernel"] = self._institutional.status()
        except Exception as e:
            return self._safe_stop(cycle, f"decision_failure:{e}", "DECISION_FAILURE")

        action = decision.action
        if action in ("NO_TRADE", "HOLD") or not decision.allowed_new_entry:
            cycle.transition(ControlState.RISK_CHECK, reason="no_entry_skip_risk_heavy")
            cycle.transition(ControlState.EXECUTION_INTENT, reason="no_intent")
            # skip paper — go monitoring → reassessment → completed
            cycle.transition(ControlState.PAPER_EXECUTION, reason="null_skip")
            cycle.transition(ControlState.MONITORING, reason="monitor")
            cycle.transition(ControlState.REASSESSMENT, reason="reassess")
            cycle.transition(ControlState.COMPLETED, reason="complete_no_entry")
            cycle.audit["paper"] = "NULL_NO_ENTRY"
            return CycleOutcome(
                cycle_id=cycle.cycle_id,
                final_state=cycle.state.value,
                action=action,
                reasons=list(decision.reasons),
                transitions=[f"{t.from_state}->{t.to_state}" for t in cycle.transitions],
                audit=cycle.to_audit(),
                broker_orders_submitted=0,
            )

        # RISK_CHECK
        cycle.transition(ControlState.RISK_CHECK, reason="paper_risk")
        risk_ok = decision.risk_allowed if hasattr(decision, "risk_allowed") else True
        if not risk_ok:
            return self._safe_stop(cycle, decision.risk_reason or "risk_halt", "RISK_FAILURE")

        # EXECUTION_INTENT — idempotent
        cycle.transition(ControlState.EXECUTION_INTENT, reason="create_intent")
        intent_id = cycle.intent_key(action)
        if intent_id in self._intent_registry or not cycle.register_intent(intent_id):
            return self._safe_stop(cycle, "duplicate_intent", "EXECUTION_CONTRACT_FAILURE")
        self._intent_registry.add(intent_id)
        if crash_after_state == "EXECUTION_INTENT":
            cycle.transition(ControlState.RECOVERY_REQUIRED, reason="crash_after_intent")
            return CycleOutcome(
                cycle_id=cycle.cycle_id,
                final_state=cycle.state.value,
                action="RECOVERY_REQUIRED",
                reasons=["crash_after_intent"],
                transitions=[f"{t.from_state}->{t.to_state}" for t in cycle.transitions],
                audit=cycle.to_audit(),
                intent_id=intent_id,
                recovery_required=True,
            )
        if cycle.is_expired(now):
            return self._safe_stop(cycle, "intent_ttl", "TIMEOUT")

        # PAPER_EXECUTION — null only via execution contract
        cycle.transition(ControlState.PAPER_EXECUTION, reason="paper_null")
        cycle.audit["paper"] = "NULL_EXECUTED"
        cycle.audit["execution_contract"] = "NULL_PAPER_PROVIDER"
        # never touch broker
        cycle.broker_orders_submitted = 0

        cycle.transition(ControlState.MONITORING, reason="monitor_paper")
        cycle.transition(ControlState.REASSESSMENT, reason="reassess")
        cycle.transition(ControlState.COMPLETED, reason="complete")

        return CycleOutcome(
            cycle_id=cycle.cycle_id,
            final_state=cycle.state.value,
            action=action,
            reasons=list(decision.reasons),
            transitions=[f"{t.from_state}->{t.to_state}" for t in cycle.transitions],
            audit=cycle.to_audit(),
            intent_id=intent_id,
            broker_orders_submitted=0,
        )
