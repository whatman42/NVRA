"""Phase 5G — N.U.N.G. paper execution orchestration. End-to-end paper pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from god.execution_contract import ExecutionContractEngine, IntentAction
from god.execution_contract.models import ExecutionIntent, IntentStatus
from god.memory.database import utc_now
from god.research.provenance import content_hash

from .lifecycle import LifecycleRecord, LifecycleState, PaperLifecycleEngine
from .models import build_paper_provenance
from .performance import PaperPerformanceEngine, PerformanceMetrics
from .portfolio import PaperPortfolioEngine, PaperPortfolioState
from .safety import PaperSafetyGate


class PipelineStatus(str, Enum):
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    RETURN_EXISTING = "RETURN_EXISTING"


SCHEMA_VERSION = "paper-orchestrator-5g-v1"


@dataclass(frozen=True)
class PaperPipelineResult:
    result_id: str
    status: PipelineStatus
    lifecycle_state: Optional[str]
    decision_id: str
    cycle_id: str
    intent_id: Optional[str]
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    lifecycle_id: Optional[str] = None
    paper_execution_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    reason_codes: tuple[str, ...] = ()
    performance: Optional[dict[str, Any]] = None
    provenance: Optional[dict[str, Any]] = None
    notes: str = "paper_pipeline_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "status": self.status.value,
            "lifecycle_state": self.lifecycle_state,
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "intent_id": self.intent_id,
            "lifecycle_id": self.lifecycle_id,
            "paper_execution_id": self.paper_execution_id,
            "portfolio_id": self.portfolio_id,
            "reason_codes": list(self.reason_codes),
            "performance": dict(self.performance) if self.performance else None,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


class PaperOrchestrator:
    """
    Canonical end-to-end paper pipeline:

      ShadowDecision
        → ExecutionIntent (5A)
        → SafetyGate / Risk (5E)
        → Lifecycle (5F) → simulate → reconcile → portfolio
        → Performance (5D)
        → PaperPipelineResult

    Simulation only. No broker. No live orders.
    """

    def __init__(
        self,
        *,
        contract: Optional[ExecutionContractEngine] = None,
        lifecycle: Optional[PaperLifecycleEngine] = None,
        portfolio: Optional[PaperPortfolioEngine] = None,
        safety: Optional[PaperSafetyGate] = None,
        max_cache: int = 500,
    ) -> None:
        self.contract = contract or ExecutionContractEngine()
        self.portfolio = portfolio or PaperPortfolioEngine()
        self.safety = safety or PaperSafetyGate()
        self.lifecycle = lifecycle or PaperLifecycleEngine(
            portfolio=self.portfolio, safety=self.safety
        )
        self.performance = PaperPerformanceEngine(self.portfolio)
        self._cache: dict[str, PaperPipelineResult] = {}
        self.max_cache = max_cache
        self._order: list[str] = []

    def run_paper_cycle(
        self,
        decision: Any,
        *,
        market_observation: Optional[dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
        data_status: str = "HEALTHY",
        now_iso: Optional[str] = None,
        max_drawdown: Optional[float] = None,
        action: IntentAction = IntentAction.PAPER_ENTER,
    ) -> PaperPipelineResult:
        now = now_iso or utc_now()
        decision_id = str(getattr(decision, "decision_id", "") or "")
        cycle_id = str(getattr(decision, "cycle_id", "") or "")

        key_payload = {
            "decision_id": decision_id,
            "cycle_id": cycle_id,
            "snapshot_id": snapshot_id or "",
            "action": action.value,
            "schema": SCHEMA_VERSION,
        }
        if market_observation:
            # fingerprint last values for identity when observation changes
            for sym, obs in market_observation.items():
                if isinstance(obs, dict) and obs.get("values"):
                    key_payload[f"v:{sym}"] = obs["values"][-1]
        rid = "pipe-" + content_hash(key_payload)[:24]
        if rid in self._cache:
            existing = self._cache[rid]
            if existing.status == PipelineStatus.COMPLETED:
                return PaperPipelineResult(
                    result_id=existing.result_id,
                    status=PipelineStatus.RETURN_EXISTING,
                    lifecycle_state=existing.lifecycle_state,
                    decision_id=existing.decision_id,
                    cycle_id=existing.cycle_id,
                    intent_id=existing.intent_id,
                    content_hash=existing.content_hash,
                    lifecycle_id=existing.lifecycle_id,
                    paper_execution_id=existing.paper_execution_id,
                    portfolio_id=existing.portfolio_id,
                    reason_codes=existing.reason_codes,
                    performance=existing.performance,
                    provenance=existing.provenance,
                    notes="return_existing",
                )

        # 1–4: intent from decision
        intent = self.contract.create_intent(decision, action=action, now_iso=now)
        # force VALID status on intent object for path when decision is SELECTED
        status_obj = getattr(decision, "status", None)
        decision_status = (
            status_obj.value if hasattr(status_obj, "value") else str(status_obj or "")
        )
        if decision_status.upper() in (
            "UNKNOWN",
            "BLOCKED",
            "INVALID",
            "STALE",
            "CORRUPTED",
        ):
            return self._reject(
                rid,
                decision_id,
                cycle_id,
                intent.intent_id,
                now,
                (f"decision_{decision_status.lower()}",),
            )

        # Rebuild intent with VALID for selected path
        from god.execution_contract.models import (
            SCHEMA_VERSION as INTENT_SCHEMA,
            build_exec_provenance,
        )

        core = {
            "decision_id": intent.decision_id,
            "cycle_id": intent.cycle_id,
            "opportunity_id": intent.opportunity_id,
            "symbol": intent.symbol,
            "strategy_ref": intent.strategy_ref,
            "decision_status": intent.decision_status,
            "intent_action": intent.intent_action.value,
            "schema_version": INTENT_SCHEMA,
        }
        valid_intent = ExecutionIntent(
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            cycle_id=intent.cycle_id,
            opportunity_id=intent.opportunity_id,
            symbol=intent.symbol,
            strategy_ref=intent.strategy_ref,
            decision_status=intent.decision_status,
            intent_action=intent.intent_action,
            intent_status=IntentStatus.VALID,
            created_at=intent.created_at,
            content_hash=content_hash(core),
            evidence_refs=intent.evidence_refs,
            provenance=build_exec_provenance(core),
        )

        # 5–14: lifecycle (includes safety, simulate, reconcile, portfolio)
        life = self.lifecycle.run(
            valid_intent,
            market_observation=market_observation,
            snapshot_id=snapshot_id,
            data_status=data_status,
            now_iso=now,
            max_drawdown=max_drawdown,
        )

        if life.state != LifecycleState.COMPLETED:
            return self._reject(
                rid,
                decision_id,
                cycle_id,
                intent.intent_id,
                now,
                life.reason_codes or (life.state.value,),
                lifecycle_id=life.lifecycle_id,
                lifecycle_state=life.state.value,
                paper_execution_id=life.paper_execution_id,
            )

        metrics = self.performance.compute()
        payload = {
            "result_id": rid,
            "status": PipelineStatus.COMPLETED.value,
            "lifecycle_id": life.lifecycle_id,
            "decision_id": decision_id,
            "cycle_id": cycle_id,
        }
        result = PaperPipelineResult(
            result_id=rid,
            status=PipelineStatus.COMPLETED,
            lifecycle_state=life.state.value,
            decision_id=decision_id,
            cycle_id=cycle_id,
            intent_id=intent.intent_id,
            content_hash=content_hash(payload),
            lifecycle_id=life.lifecycle_id,
            paper_execution_id=life.paper_execution_id,
            portfolio_id=life.portfolio_id,
            reason_codes=("pipeline_completed",),
            performance=metrics.to_dict(),
            provenance=build_paper_provenance(payload),
        )
        return self._store(result)

    def _reject(
        self,
        rid: str,
        decision_id: str,
        cycle_id: str,
        intent_id: Optional[str],
        now: str,
        reasons: tuple[str, ...],
        *,
        lifecycle_id: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        paper_execution_id: Optional[str] = None,
    ) -> PaperPipelineResult:
        payload = {
            "result_id": rid,
            "status": PipelineStatus.REJECTED.value,
            "reasons": list(reasons),
        }
        result = PaperPipelineResult(
            result_id=rid,
            status=PipelineStatus.REJECTED,
            lifecycle_state=lifecycle_state,
            decision_id=decision_id,
            cycle_id=cycle_id,
            intent_id=intent_id,
            content_hash=content_hash(payload),
            lifecycle_id=lifecycle_id,
            paper_execution_id=paper_execution_id,
            reason_codes=reasons,
            provenance=build_paper_provenance(payload),
            notes="paper_pipeline_rejected",
        )
        return self._store(result)

    def _store(self, result: PaperPipelineResult) -> PaperPipelineResult:
        self._cache[result.result_id] = result
        if result.result_id not in self._order:
            self._order.append(result.result_id)
        while len(self._order) > self.max_cache:
            old = self._order.pop(0)
            self._cache.pop(old, None)
        return result
