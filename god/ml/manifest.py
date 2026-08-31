"""Artifact manifest — deterministic, verifiable model deployment metadata.

Fail-closed on incomplete/corrupt manifests. Never enables LIVE.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .lifecycle import ARTIFACT_SCHEMA_VERSION, atomic_write_text, file_sha256
from .persist import ArtifactBundle

MANIFEST_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass
class ArtifactManifest:
    """Full deployment manifest for a model artifact."""

    manifest_version: str = MANIFEST_VERSION
    schema_version: str = ARTIFACT_SCHEMA_VERSION
    model_id: str = ""
    model_version: str = ""
    model_family: str = ""
    backend: str = ""
    status: str = "candidate"
    feature_schema_version: str = ""
    feature_schema_hash: str = ""
    feature_names: list[str] = field(default_factory=list)
    dataset_fingerprint: str = ""
    dataset_version: str = ""
    n_samples: int = 0
    trained_at: str = ""
    promoted_at: str = ""
    parent_champion_id: str = ""
    parent_champion_version: str = ""
    artifact_checksum: str = ""
    calibration_method: str = ""
    calibration_version: str = ""
    calibration_n: int = 0
    calibration_checksum: str = ""
    oos_metrics: dict[str, float] = field(default_factory=dict)
    hardware_profile: str = ""
    runtime_python: str = ""
    runtime_platform: str = ""
    runtime_arch: str = ""
    library_versions: dict[str, str] = field(default_factory=dict)
    rollback_from_id: str = ""
    rollback_from_version: str = ""
    rollback_reason: str = ""
    notes: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "model_family": self.model_family,
            "backend": self.backend,
            "status": self.status,
            "feature_schema_version": self.feature_schema_version,
            "feature_schema_hash": self.feature_schema_hash,
            "feature_names": list(self.feature_names),
            "dataset_fingerprint": self.dataset_fingerprint,
            "dataset_version": self.dataset_version,
            "n_samples": self.n_samples,
            "trained_at": self.trained_at,
            "promoted_at": self.promoted_at,
            "parent_champion_id": self.parent_champion_id,
            "parent_champion_version": self.parent_champion_version,
            "artifact_checksum": self.artifact_checksum,
            "calibration_method": self.calibration_method,
            "calibration_version": self.calibration_version,
            "calibration_n": self.calibration_n,
            "calibration_checksum": self.calibration_checksum,
            "oos_metrics": dict(self.oos_metrics),
            "hardware_profile": self.hardware_profile,
            "runtime_python": self.runtime_python,
            "runtime_platform": self.runtime_platform,
            "runtime_arch": self.runtime_arch,
            "library_versions": dict(self.library_versions),
            "rollback_from_id": self.rollback_from_id,
            "rollback_from_version": self.rollback_from_version,
            "rollback_reason": self.rollback_reason,
            "notes": list(self.notes),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ArtifactManifest":
        return cls(
            manifest_version=str(d.get("manifest_version", MANIFEST_VERSION)),
            schema_version=str(d.get("schema_version", ARTIFACT_SCHEMA_VERSION)),
            model_id=str(d.get("model_id", "")),
            model_version=str(d.get("model_version", "")),
            model_family=str(d.get("model_family", "")),
            backend=str(d.get("backend", "")),
            status=str(d.get("status", "candidate")),
            feature_schema_version=str(d.get("feature_schema_version", "")),
            feature_schema_hash=str(d.get("feature_schema_hash", "")),
            feature_names=list(d.get("feature_names") or []),
            dataset_fingerprint=str(d.get("dataset_fingerprint", "")),
            dataset_version=str(d.get("dataset_version", "")),
            n_samples=int(d.get("n_samples", 0)),
            trained_at=str(d.get("trained_at", "")),
            promoted_at=str(d.get("promoted_at", "")),
            parent_champion_id=str(d.get("parent_champion_id", "")),
            parent_champion_version=str(d.get("parent_champion_version", "")),
            artifact_checksum=str(d.get("artifact_checksum", "")),
            calibration_method=str(d.get("calibration_method", "")),
            calibration_version=str(d.get("calibration_version", "")),
            calibration_n=int(d.get("calibration_n", 0)),
            calibration_checksum=str(d.get("calibration_checksum", "")),
            oos_metrics={str(k): float(v) for k, v in (d.get("oos_metrics") or {}).items()},
            hardware_profile=str(d.get("hardware_profile", "")),
            runtime_python=str(d.get("runtime_python", "")),
            runtime_platform=str(d.get("runtime_platform", "")),
            runtime_arch=str(d.get("runtime_arch", "")),
            library_versions={str(k): str(v) for k, v in (d.get("library_versions") or {}).items()},
            rollback_from_id=str(d.get("rollback_from_id", "")),
            rollback_from_version=str(d.get("rollback_from_version", "")),
            rollback_reason=str(d.get("rollback_reason", "")),
            notes=list(d.get("notes") or []),
            created_at=str(d.get("created_at", "")),
        )


def feature_schema_hash(feature_names: list[str] | tuple[str, ...], features_version: str) -> str:
    payload = (features_version + "|" + ",".join(feature_names)).encode("utf-8")
    return _stable_hash(payload)[:32]


def detect_library_versions() -> dict[str, str]:
    out: dict[str, str] = {"python": sys.version.split()[0]}
    for name in ("numpy", "sklearn", "lightgbm", "xgboost", "catboost", "torch", "shap"):
        try:
            mod = __import__(name if name != "sklearn" else "sklearn")
            ver = getattr(mod, "__version__", "unknown")
            out[name] = str(ver)
        except Exception:
            pass
    return out


def build_manifest_from_bundle(
    bundle: ArtifactBundle,
    *,
    status: str = "candidate",
    model_family: str = "",
    hardware_profile: str = "",
    oos_metrics: Optional[dict[str, float]] = None,
    parent_champion_id: str = "",
    parent_champion_version: str = "",
    calibration_method: str = "",
    calibration_n: int = 0,
    n_samples: int = 0,
) -> ArtifactManifest:
    names = list(bundle.feature_names)
    cal = bundle.calibration or {}
    method = calibration_method or str(cal.get("method", cal.get("status", "")))
    cal_n = calibration_n or int(cal.get("n", 0) or 0)
    cal_cs = ""
    if cal:
        cal_cs = _stable_hash(json.dumps(cal, sort_keys=True).encode())[:32]
    return ArtifactManifest(
        model_id=bundle.model_id,
        model_version=bundle.model_version,
        model_family=model_family or bundle.model_id,
        backend=bundle.backend,
        status=status,
        feature_schema_version=bundle.features_version,
        feature_schema_hash=feature_schema_hash(names, bundle.features_version),
        feature_names=names,
        dataset_fingerprint=bundle.dataset_hash,
        n_samples=n_samples or int(bundle.metrics.get("n_samples", 0) or 0),
        trained_at=bundle.saved_at or _utc_now(),
        parent_champion_id=parent_champion_id,
        parent_champion_version=parent_champion_version,
        artifact_checksum=bundle.artifact_checksum,
        calibration_method=method,
        calibration_version="1",
        calibration_n=cal_n,
        calibration_checksum=cal_cs,
        oos_metrics=dict(oos_metrics or bundle.metrics or {}),
        hardware_profile=hardware_profile or str((bundle.metadata or {}).get("hardware_profile", "")),
        runtime_python=sys.version.split()[0],
        runtime_platform=platform.system(),
        runtime_arch=platform.machine(),
        library_versions=detect_library_versions(),
        created_at=_utc_now(),
        schema_version=bundle.schema_version or ARTIFACT_SCHEMA_VERSION,
    )


def validate_manifest(m: ArtifactManifest) -> tuple[bool, str]:
    if not m.model_id or not m.model_version:
        return False, "missing_model_identity"
    if not m.artifact_checksum:
        return False, "missing_artifact_checksum"
    if not m.feature_names:
        return False, "missing_feature_names"
    if not m.dataset_fingerprint:
        return False, "missing_dataset_fingerprint"
    if m.schema_version and m.schema_version != ARTIFACT_SCHEMA_VERSION:
        return False, f"unsupported_schema:{m.schema_version}"
    if m.manifest_version and m.manifest_version.split(".")[0] != MANIFEST_VERSION.split(".")[0]:
        return False, f"unsupported_manifest:{m.manifest_version}"
    return True, "ok"


def save_manifest(root: Path, manifest: ArtifactManifest) -> Path:
    root = Path(root)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in manifest.model_id)
    safe_ver = "".join(c if c.isalnum() or c in "._-" else "_" for c in manifest.model_version)
    mdir = root / "artifacts" / f"{safe_id}@{safe_ver}"
    mdir.mkdir(parents=True, exist_ok=True)
    path = mdir / "manifest.json"
    atomic_write_text(path, json.dumps(manifest.to_dict(), indent=2))
    return path


def load_manifest(root: Path, model_id: str, model_version: str) -> Optional[ArtifactManifest]:
    root = Path(root)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in model_id)
    safe_ver = "".join(c if c.isalnum() or c in "._-" else "_" for c in model_version)
    path = root / "artifacts" / f"{safe_id}@{safe_ver}" / "manifest.json"
    if not path.is_file():
        return None
    try:
        return ArtifactManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
        return None


def verify_manifest_against_disk(
    root: Path, model_id: str, model_version: str
) -> tuple[bool, str, Optional[ArtifactManifest]]:
    """Validate manifest + on-disk checksum consistency. Fail-closed."""
    m = load_manifest(root, model_id, model_version)
    if m is None:
        return False, "manifest_missing_or_corrupt", None
    ok, reason = validate_manifest(m)
    if not ok:
        return False, reason, m
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in model_id)
    safe_ver = "".join(c if c.isalnum() or c in "._-" else "_" for c in model_version)
    art = root / "artifacts" / f"{safe_id}@{safe_ver}" / "model.pkl"
    if not art.is_file():
        return False, "artifact_missing", m
    actual = file_sha256(art)
    if m.artifact_checksum and actual != m.artifact_checksum:
        return False, "checksum_mismatch", m
    return True, "ok", m
