"""Artifact validation gate before Model Registry promotion.

Providers only produce artifacts; NVRA decides promotion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .types import JobStatus, TrainingJob, TrainingResult


@dataclass
class ArtifactValidationResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    eligible_for_promotion: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "eligible_for_promotion": self.eligible_for_promotion,
        }


def validate_training_result(
    result: TrainingResult,
    *,
    expected_dataset_hash: str = "",
    expected_schema: Optional[Mapping[str, Any]] = None,
    min_artifact_hash_len: int = 16,
) -> ArtifactValidationResult:
    """Fail-closed validation. INTERRUPTED/UNKNOWN/FAILED never promote."""
    reasons: list[str] = []
    job = result.job

    if job.status != JobStatus.SUCCESS:
        reasons.append(f"job_status_not_success:{job.status.value}")

    if not result.artifact_hash or len(result.artifact_hash) < min_artifact_hash_len:
        reasons.append("missing_or_short_artifact_hash")

    if expected_dataset_hash and job.dataset_hash and job.dataset_hash != expected_dataset_hash:
        reasons.append("dataset_hash_mismatch")

    if expected_schema:
        meta = job.metadata or {}
        for key, value in expected_schema.items():
            if meta.get(key) != value:
                reasons.append(f"schema_mismatch:{key}")

    # Cloud notes that indicate incomplete external sessions
    if "interrupted" in result.provider_notes or "not_success" in result.provider_notes:
        reasons.append("provider_interrupted")

    ok = not reasons
    return ArtifactValidationResult(
        ok=ok,
        reasons=reasons,
        eligible_for_promotion=ok,
    )


def reject_promotion_if_invalid(result: TrainingResult, **kwargs: Any) -> ArtifactValidationResult:
    return validate_training_result(result, **kwargs)
