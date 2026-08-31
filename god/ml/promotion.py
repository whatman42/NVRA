"""Champion / challenger promotion gates — OOS evidence only.

Hardware changes alone MUST NOT promote. Explicit gates required.
Transactional promotion: all checks pass then atomic champion swap.
Crash before commit → old champion remains.
Statuses: candidate | challenger | champion | retired | rolled_back
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .benchmark import BenchmarkMetrics, FamilyBenchmark
from .drift import DriftReport
from .lifecycle import verify_artifact_integrity
from .manifest import verify_manifest_against_disk, load_manifest, save_manifest
from .registry import ModelRecord, ModelRegistry
from .state_machine import apply_transition, CHAMPION, CHALLENGER, PROMOTION_GATE, CANDIDATE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PromotionGateResult:
    allowed: bool
    reason: str
    challenger_id: str = ""
    challenger_version: str = ""
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "challenger_id": self.challenger_id,
            "challenger_version": self.challenger_version,
            "metrics": dict(self.metrics),
        }


@dataclass
class PromotionPolicy:
    min_oos_accuracy: float = 0.52
    min_oos_n: int = 20
    max_brier: float = 0.30
    min_improvement: float = 0.01  # vs champion accuracy
    require_calibration: bool = False
    block_on_drift: bool = True


@dataclass
class RollbackResult:
    success: bool
    reason: str = ""
    restored_id: str = ""
    restored_version: str = ""
    demoted_id: str = ""
    demoted_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "reason": self.reason,
            "restored_id": self.restored_id,
            "restored_version": self.restored_version,
            "demoted_id": self.demoted_id,
            "demoted_version": self.demoted_version,
        }


@dataclass
class TransactionalPromotionResult:
    success: bool
    reason: str = ""
    champion_id: str = ""
    champion_version: str = ""
    previous_id: str = ""
    previous_version: str = ""
    steps_completed: list[str] = field(default_factory=list)
    prefer_no_trade: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "reason": self.reason,
            "champion_id": self.champion_id,
            "champion_version": self.champion_version,
            "previous_id": self.previous_id,
            "previous_version": self.previous_version,
            "steps_completed": list(self.steps_completed),
            "prefer_no_trade": self.prefer_no_trade,
        }


def evaluate_promotion(
    challenger: ModelRecord,
    *,
    champion: Optional[ModelRecord] = None,
    challenger_oos: Optional[BenchmarkMetrics] = None,
    drift: Optional[DriftReport] = None,
    policy: Optional[PromotionPolicy] = None,
    hardware_only: bool = False,
) -> PromotionGateResult:
    """Decide whether challenger may become champion."""
    pol = policy or PromotionPolicy()

    if hardware_only:
        return PromotionGateResult(
            allowed=False,
            reason="hardware_change_alone_cannot_promote",
            challenger_id=challenger.model_id,
            challenger_version=challenger.model_version,
        )

    if drift is not None and pol.block_on_drift and drift.restrict_promotion:
        return PromotionGateResult(
            allowed=False,
            reason="drift_restricts_promotion",
            challenger_id=challenger.model_id,
            challenger_version=challenger.model_version,
            metrics={"confidence_multiplier": drift.confidence_multiplier},
        )

    oos = challenger_oos
    acc = 0.0
    brier = 1.0
    n = 0
    if oos is not None:
        acc, brier, n = oos.accuracy, oos.brier, oos.n
    else:
        acc = float(challenger.oos_metrics.get("accuracy", challenger.metrics.get("oos_acc", 0.0)))
        brier = float(challenger.oos_metrics.get("brier", challenger.metrics.get("brier", 1.0)))
        n = int(challenger.oos_metrics.get("n", challenger.metrics.get("n", 0)))

    if n < pol.min_oos_n:
        return PromotionGateResult(
            allowed=False,
            reason="insufficient_oos_n",
            challenger_id=challenger.model_id,
            challenger_version=challenger.model_version,
            metrics={"n": float(n), "min_n": float(pol.min_oos_n)},
        )

    if acc < pol.min_oos_accuracy:
        return PromotionGateResult(
            allowed=False,
            reason="oos_accuracy_below_threshold",
            challenger_id=challenger.model_id,
            challenger_version=challenger.model_version,
            metrics={"accuracy": acc, "min_accuracy": pol.min_oos_accuracy},
        )

    if brier > pol.max_brier:
        return PromotionGateResult(
            allowed=False,
            reason="brier_too_high",
            challenger_id=challenger.model_id,
            challenger_version=challenger.model_version,
            metrics={"brier": brier, "max_brier": pol.max_brier},
        )

    if champion is not None:
        # Compare like-for-like OOS evidence only. A champion with no OOS
        # accuracy must not be judged against its in-sample/train accuracy;
        # doing so makes a valid challenger impossible to promote merely
        # because the incumbent was trained on a different sample.
        champion_oos_acc = champion.oos_metrics.get("accuracy")
        if champion_oos_acc is None:
            champion_oos_acc = champion.metrics.get("oos_acc")
        if champion_oos_acc is not None:
            champ_acc = float(champion_oos_acc)
            if acc < champ_acc + pol.min_improvement:
                return PromotionGateResult(
                    allowed=False,
                    reason="no_meaningful_improvement_vs_champion",
                    challenger_id=challenger.model_id,
                    challenger_version=challenger.model_version,
                    metrics={"challenger_acc": acc, "champion_acc": champ_acc},
                )

    if pol.require_calibration and challenger.calibration_status not in ("VALID", "valid"):
        return PromotionGateResult(
            allowed=False,
            reason="calibration_required_not_valid",
            challenger_id=challenger.model_id,
            challenger_version=challenger.model_version,
        )

    return PromotionGateResult(
        allowed=True,
        reason="oos_gates_passed",
        challenger_id=challenger.model_id,
        challenger_version=challenger.model_version,
        metrics={"accuracy": acc, "brier": brier, "n": float(n)},
    )


def try_promote(
    registry: ModelRegistry,
    model_id: str,
    model_version: str,
    *,
    challenger_oos: Optional[BenchmarkMetrics] = None,
    drift: Optional[DriftReport] = None,
    policy: Optional[PromotionPolicy] = None,
) -> PromotionGateResult:
    """Evaluate and, if allowed, promote challenger to champion."""
    rec = None
    for r in registry.list_models():
        if r.model_id == model_id and r.model_version == model_version:
            rec = r
            break
    if rec is None:
        return PromotionGateResult(
            allowed=False,
            reason="model_not_found",
            challenger_id=model_id,
            challenger_version=model_version,
        )

    gate = evaluate_promotion(
        rec,
        champion=registry.champion(),
        challenger_oos=challenger_oos,
        drift=drift,
        policy=policy,
    )
    if gate.allowed:
        registry.promote_champion(model_id, model_version)
        gate.reason = "promoted:" + gate.reason
    return gate


def transactional_promote(
    registry: ModelRegistry,
    model_id: str,
    model_version: str,
    *,
    challenger_oos: Optional[BenchmarkMetrics] = None,
    drift: Optional[DriftReport] = None,
    policy: Optional[PromotionPolicy] = None,
    audit: Any = None,
) -> TransactionalPromotionResult:
    """Atomic promotion: validate all gates, then swap champion pointer once.

    If any pre-commit check fails, old champion remains active.
    """
    steps: list[str] = []
    rec = None
    for r in registry.list_models():
        if r.model_id == model_id and r.model_version == model_version:
            rec = r
            break
    if rec is None:
        return TransactionalPromotionResult(success=False, reason="model_not_found")

    steps.append("candidate_found")
    prev = registry.champion()
    prev_id = prev.model_id if prev else ""
    prev_ver = prev.model_version if prev else ""

    # State machine: candidate/challenger → promotion_gate
    tr = apply_transition(
        rec.status, PROMOTION_GATE,
        model_id=model_id, model_version=model_version, audit=audit,
    )
    if not tr.allowed and rec.status not in (CANDIDATE, CHALLENGER, "candidate", "challenger"):
        return TransactionalPromotionResult(
            success=False,
            reason=f"illegal_status:{rec.status}",
            steps_completed=steps,
        )
    steps.append("state_ok")

    # Integrity
    irep = verify_artifact_integrity(registry.root, model_id, model_version)
    if not irep.ok:
        return TransactionalPromotionResult(
            success=False,
            reason=f"integrity_failed:{irep.status}",
            steps_completed=steps,
            prefer_no_trade=True,
        )
    steps.append("integrity_ok")

    # Manifest (optional soft — missing allowed, mismatch not)
    mok, mreason, _ = verify_manifest_against_disk(registry.root, model_id, model_version)
    if not mok and mreason not in ("manifest_missing_or_corrupt",):
        return TransactionalPromotionResult(
            success=False,
            reason=f"manifest_failed:{mreason}",
            steps_completed=steps,
        )
    steps.append("manifest_ok")

    # OOS / policy gates
    gate = evaluate_promotion(
        rec,
        champion=prev,
        challenger_oos=challenger_oos,
        drift=drift,
        policy=policy,
    )
    if not gate.allowed:
        return TransactionalPromotionResult(
            success=False,
            reason=gate.reason,
            steps_completed=steps,
        )
    steps.append("oos_gate_ok")

    # Commit: single registry mutation
    registry.promote_champion(model_id, model_version)
    steps.append("champion_pointer_updated")

    # Post-promotion verification
    new_champ = registry.champion()
    if new_champ is None or new_champ.model_id != model_id or new_champ.model_version != model_version:
        # Attempt restore of previous if pointer wrong (should not happen)
        if prev is not None:
            try:
                registry.promote_champion(prev.model_id, prev.model_version)
            except Exception:
                pass
        return TransactionalPromotionResult(
            success=False,
            reason="post_promotion_verify_failed",
            steps_completed=steps,
            prefer_no_trade=True,
        )
    steps.append("post_verify_ok")

    # Update manifest status if present
    man = load_manifest(registry.root, model_id, model_version)
    if man is not None:
        man.status = "champion"
        man.promoted_at = _utc_now()
        man.parent_champion_id = prev_id
        man.parent_champion_version = prev_ver
        try:
            save_manifest(registry.root, man)
            steps.append("manifest_updated")
        except OSError:
            pass

    apply_transition(
        PROMOTION_GATE, CHAMPION,
        model_id=model_id, model_version=model_version, audit=audit,
    )

    if audit is not None:
        try:
            audit.record(
                "promote",
                model_id=model_id,
                model_version=model_version,
                outcome="success",
                detail={
                    "previous": f"{prev_id}@{prev_ver}",
                    "steps": steps,
                    "metrics": gate.metrics,
                },
            )
        except Exception:
            pass

    return TransactionalPromotionResult(
        success=True,
        reason="promoted_transactional",
        champion_id=model_id,
        champion_version=model_version,
        previous_id=prev_id,
        previous_version=prev_ver,
        steps_completed=steps,
    )


def evaluate_rollback(
    *,
    champion: Optional[ModelRecord] = None,
    previous: Optional[ModelRecord] = None,
    performance_collapse: bool = False,
    abnormal_drift: bool = False,
    calibration_failure: bool = False,
    runtime_failure: bool = False,
    resource_failure: bool = False,
    instability: bool = False,
) -> RollbackResult:
    """Decide whether rollback is warranted. Fail-closed if no previous champion."""
    if not any(
        [
            performance_collapse,
            abnormal_drift,
            calibration_failure,
            runtime_failure,
            resource_failure,
            instability,
        ]
    ):
        return RollbackResult(success=False, reason="no_rollback_trigger")

    if previous is None:
        return RollbackResult(success=False, reason="no_previous_champion")

    if champion is None:
        return RollbackResult(
            success=True,
            reason="restore_previous_no_current_champion",
            restored_id=previous.model_id,
            restored_version=previous.model_version,
        )

    return RollbackResult(
        success=True,
        reason="rollback_trigger_active",
        restored_id=previous.model_id,
        restored_version=previous.model_version,
        demoted_id=champion.model_id,
        demoted_version=champion.model_version,
    )


def try_rollback(
    registry: ModelRegistry,
    *,
    performance_collapse: bool = False,
    abnormal_drift: bool = False,
    calibration_failure: bool = False,
    runtime_failure: bool = False,
    resource_failure: bool = False,
    instability: bool = False,
) -> RollbackResult:
    """Evaluate and, if allowed, restore previous champion. Deterministic + fail-closed."""
    champ = registry.champion()
    prev = registry.previous_champion()
    decision = evaluate_rollback(
        champion=champ,
        previous=prev,
        performance_collapse=performance_collapse,
        abnormal_drift=abnormal_drift,
        calibration_failure=calibration_failure,
        runtime_failure=runtime_failure,
        resource_failure=resource_failure,
        instability=instability,
    )
    if not decision.success:
        return decision

    if champ is not None:
        for r in registry._records:
            if r.model_id == champ.model_id and r.model_version == champ.model_version:
                r.status = "rolled_back"
                break

    restored = None
    for r in registry._records:
        if r.model_id == prev.model_id and r.model_version == prev.model_version:
            r.status = "champion"
            restored = r
            break

    if restored is None:
        return RollbackResult(success=False, reason="previous_record_missing")

    registry._save()
    return RollbackResult(
        success=True,
        reason="rolled_back_to_previous",
        restored_id=restored.model_id,
        restored_version=restored.model_version,
        demoted_id=champ.model_id if champ else "",
        demoted_version=champ.model_version if champ else "",
    )
