"""Artifact validation gate before Model Registry promotion.

Providers only produce artifacts; NVRA decides promotion.
Fail-closed: missing/mismatched hashes and unresolvable artifacts never promote.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Union
from urllib.parse import urlparse

from .types import JobStatus, TrainingResult

PathLike = Union[str, Path]


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


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_artifact_path(
    result: TrainingResult,
    *,
    artifact_path: Optional[PathLike] = None,
) -> Optional[Path]:
    """Resolve a filesystem path for the training artifact, if possible."""
    if artifact_path is not None:
        p = Path(artifact_path)
        return p if p.is_file() else None

    meta_path = (result.job.metadata or {}).get("artifact_path")
    if meta_path:
        p = Path(str(meta_path))
        if p.is_file():
            return p

    ref = result.job.artifact_ref or ""
    if not ref:
        return None
    # local://job_id/hash or plain filesystem path
    if ref.startswith("local://"):
        # Prefer explicit path in metadata; bare local:// without path is unresolvable
        return None
    if "://" in ref:
        parsed = urlparse(ref)
        if parsed.scheme in ("file", ""):
            p = Path(parsed.path)
            return p if p.is_file() else None
        return None
    p = Path(ref)
    return p if p.is_file() else None


def validate_training_result(
    result: TrainingResult,
    *,
    expected_dataset_hash: str = "",
    expected_schema: Optional[Mapping[str, Any]] = None,
    min_artifact_hash_len: int = 16,
    artifact_path: Optional[PathLike] = None,
    artifact_bytes: Optional[bytes] = None,
    require_resolvable_artifact: bool = True,
) -> ArtifactValidationResult:
    """Fail-closed validation. INTERRUPTED/UNKNOWN/FAILED never promote.

    Dataset provenance: when *expected_dataset_hash* is provided (non-empty),
    *job.dataset_hash* must match exactly — empty/missing job hash is REJECT.

    Artifact integrity: when *require_resolvable_artifact* is True (default),
    the artifact must be resolvable as bytes or an on-disk file whose SHA-256
    matches *result.artifact_hash*. Unresolvable artifact → REJECT.
    """
    reasons: list[str] = []
    job = result.job

    if job.status != JobStatus.SUCCESS:
        reasons.append(f"job_status_not_success:{job.status.value}")

    if not result.artifact_hash or len(result.artifact_hash) < min_artifact_hash_len:
        reasons.append("missing_or_short_artifact_hash")

    # Strict dataset provenance
    if expected_dataset_hash:
        if not job.dataset_hash:
            reasons.append("missing_dataset_hash")
        elif job.dataset_hash != expected_dataset_hash:
            reasons.append("dataset_hash_mismatch")

    if expected_schema:
        meta = job.metadata or {}
        for key, value in expected_schema.items():
            if meta.get(key) != value:
                reasons.append(f"schema_mismatch:{key}")

    if "interrupted" in result.provider_notes or "not_success" in result.provider_notes:
        reasons.append("provider_interrupted")

    # Real artifact integrity
    actual_hash: Optional[str] = None
    if artifact_bytes is not None:
        actual_hash = _sha256_bytes(artifact_bytes)
    else:
        path = resolve_artifact_path(result, artifact_path=artifact_path)
        if path is not None:
            try:
                actual_hash = _sha256_file(path)
            except OSError:
                reasons.append("artifact_unreadable")
        elif require_resolvable_artifact:
            reasons.append("artifact_unresolvable")

    if actual_hash is not None and result.artifact_hash:
        if actual_hash != result.artifact_hash:
            reasons.append("artifact_hash_mismatch")

    ok = not reasons
    return ArtifactValidationResult(
        ok=ok,
        reasons=reasons,
        eligible_for_promotion=ok,
    )


def reject_promotion_if_invalid(result: TrainingResult, **kwargs: Any) -> ArtifactValidationResult:
    return validate_training_result(result, **kwargs)
