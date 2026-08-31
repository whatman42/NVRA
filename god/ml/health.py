"""Model health monitoring + composite health score.

Health is advisory evidence only — never auto-promotes, never enables LIVE.
Does not bypass Risk Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .registry import ModelRecord, ModelRegistry
from .telemetry import MLTelemetry, TelemetrySummary


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HealthReport:
    status: str  # HEALTHY | DEGRADED | CRITICAL | UNKNOWN
    champion_id: str = ""
    champion_version: str = ""
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    health_score: float = 0.0  # 0..1 deterministic composite
    checked_at: str = ""
    restrict_promotion: bool = False
    prefer_no_trade: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "champion_id": self.champion_id,
            "champion_version": self.champion_version,
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
            "health_score": self.health_score,
            "checked_at": self.checked_at,
            "restrict_promotion": self.restrict_promotion,
            "prefer_no_trade": self.prefer_no_trade,
        }


@dataclass
class HealthPolicy:
    max_block_rate: float = 0.85
    min_mean_confidence: float = 0.05
    max_p95_latency_ms: float = 5000.0
    min_inference_count_for_stats: int = 5
    min_health_score: float = 0.35


def compute_health_score(
    *,
    oos_accuracy: Optional[float] = None,
    brier: Optional[float] = None,
    f1: Optional[float] = None,
    drift_score: Optional[float] = None,  # 0 good .. 1 bad
    data_quality_score: Optional[float] = None,  # 0..1 good
    calibration_valid: Optional[bool] = None,
    uncertainty_high: bool = False,
    ood_rate: Optional[float] = None,
    p95_latency_ms: Optional[float] = None,
    artifact_ok: bool = True,
    block_rate: Optional[float] = None,
    mean_confidence: Optional[float] = None,
    model_stale: bool = False,
    recovery_failed: bool = False,
) -> float:
    """Deterministic 0..1 health score. Missing signals are neutral (skipped)."""
    parts: list[tuple[float, float]] = []  # (value 0..1, weight)

    if oos_accuracy is not None:
        v = max(0.0, min(1.0, (float(oos_accuracy) - 0.45) / 0.25))
        parts.append((v, 1.5))
    if brier is not None:
        v = max(0.0, min(1.0, 1.0 - float(brier) / 0.35))
        parts.append((v, 1.0))
    if f1 is not None:
        parts.append((max(0.0, min(1.0, float(f1))), 1.0))
    if drift_score is not None:
        parts.append((max(0.0, min(1.0, 1.0 - float(drift_score))), 1.2))
    if data_quality_score is not None:
        parts.append((max(0.0, min(1.0, float(data_quality_score))), 1.0))
    if calibration_valid is not None:
        parts.append((1.0 if calibration_valid else 0.2, 0.8))
    if uncertainty_high:
        parts.append((0.3, 0.6))
    if ood_rate is not None:
        parts.append((max(0.0, min(1.0, 1.0 - float(ood_rate))), 0.8))
    if p95_latency_ms is not None:
        v = max(0.0, min(1.0, 1.0 - (float(p95_latency_ms) - 500.0) / 4500.0))
        parts.append((v, 0.5))
    if not artifact_ok:
        parts.append((0.0, 2.0))
    if block_rate is not None:
        parts.append((max(0.0, min(1.0, 1.0 - float(block_rate))), 1.0))
    if mean_confidence is not None:
        parts.append((max(0.0, min(1.0, float(mean_confidence))), 0.7))
    if model_stale:
        parts.append((0.25, 1.0))
    if recovery_failed:
        parts.append((0.0, 1.5))

    if not parts:
        return 0.5
    total_w = sum(w for _, w in parts)
    return sum(v * w for v, w in parts) / total_w


class ModelHealthMonitor:
    """Evaluate champion + telemetry health. Fail-closed on missing data."""

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        telemetry: Optional[MLTelemetry] = None,
        policy: Optional[HealthPolicy] = None,
    ) -> None:
        self.registry = registry
        self.telemetry = telemetry or MLTelemetry()
        self.policy = policy or HealthPolicy()

    def evaluate(
        self,
        *,
        recent_oos_accuracy: Optional[float] = None,
        recent_brier: Optional[float] = None,
        recent_f1: Optional[float] = None,
        drift_restrict: bool = False,
        drift_score: Optional[float] = None,
        data_quality_score: Optional[float] = None,
        calibration_invalid: bool = False,
        uncertainty_high: bool = False,
        ood_rate: Optional[float] = None,
        artifact_ok: bool = True,
        model_stale: bool = False,
        recovery_failed: bool = False,
    ) -> HealthReport:
        reasons: list[str] = []
        metrics: dict[str, float] = {}
        champ: Optional[ModelRecord] = None
        if self.registry is not None:
            champ = self.registry.champion()

        if champ is None:
            return HealthReport(
                status="UNKNOWN",
                reasons=["no_champion"],
                health_score=0.0,
                checked_at=_utc_now(),
                prefer_no_trade=True,
            )

        summary = self.telemetry.summary()
        metrics["inference_count"] = float(summary.inference_count)
        metrics["mean_latency_ms"] = summary.mean_latency_ms
        metrics["p95_latency_ms"] = summary.p95_latency_ms
        metrics["mean_confidence"] = summary.mean_confidence
        metrics["block_rate"] = summary.block_rate

        status = "HEALTHY"
        restrict = False
        no_trade = False

        if summary.inference_count >= self.policy.min_inference_count_for_stats:
            if summary.block_rate >= self.policy.max_block_rate:
                reasons.append("high_block_rate")
                status = "DEGRADED"
                no_trade = True
            if summary.mean_confidence < self.policy.min_mean_confidence:
                reasons.append("low_mean_confidence")
                status = "DEGRADED"
                no_trade = True
            if summary.p95_latency_ms > self.policy.max_p95_latency_ms:
                reasons.append("high_p95_latency")
                if status == "HEALTHY":
                    status = "DEGRADED"

        if recent_oos_accuracy is not None:
            metrics["recent_oos_accuracy"] = float(recent_oos_accuracy)
            if recent_oos_accuracy < 0.48:
                reasons.append("oos_accuracy_collapse")
                status = "CRITICAL"
                restrict = True
                no_trade = True

        if drift_restrict:
            reasons.append("drift_restrict")
            restrict = True
            if status == "HEALTHY":
                status = "DEGRADED"

        if calibration_invalid:
            reasons.append("calibration_invalid")
            if status == "HEALTHY":
                status = "DEGRADED"
            no_trade = True

        if not artifact_ok:
            reasons.append("artifact_integrity_failed")
            status = "CRITICAL"
            restrict = True
            no_trade = True

        if model_stale:
            reasons.append("model_stale")
            if status == "HEALTHY":
                status = "DEGRADED"

        if recovery_failed:
            reasons.append("recovery_failed")
            status = "CRITICAL"
            no_trade = True
            restrict = True

        score = compute_health_score(
            oos_accuracy=recent_oos_accuracy,
            brier=recent_brier,
            f1=recent_f1,
            drift_score=drift_score if drift_score is not None else (0.8 if drift_restrict else None),
            data_quality_score=data_quality_score,
            calibration_valid=(not calibration_invalid) if calibration_invalid or recent_oos_accuracy is not None else None,
            uncertainty_high=uncertainty_high,
            ood_rate=ood_rate,
            p95_latency_ms=summary.p95_latency_ms if summary.inference_count else None,
            artifact_ok=artifact_ok,
            block_rate=summary.block_rate if summary.inference_count else None,
            mean_confidence=summary.mean_confidence if summary.inference_count else None,
            model_stale=model_stale,
            recovery_failed=recovery_failed,
        )
        metrics["health_score"] = score

        if score < self.policy.min_health_score and status == "HEALTHY":
            status = "DEGRADED"
            reasons.append("low_health_score")

        return HealthReport(
            status=status,
            champion_id=champ.model_id,
            champion_version=champ.model_version,
            reasons=reasons,
            metrics=metrics,
            health_score=score,
            checked_at=_utc_now(),
            restrict_promotion=restrict,
            prefer_no_trade=no_trade,
        )
