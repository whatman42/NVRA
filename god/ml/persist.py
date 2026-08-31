"""ML model artifact persistence — train → save → reload → predict.

Supports numpy_logit (always) and sklearn (when available).
Corrupt / missing artifacts fail closed. Never grants LIVE authority.

Lifecycle hardening:
  - schema_version on every bundle
  - artifact content checksum (sha256)
  - atomic writes (temp + replace)
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .calibration import PlattCalibrator, CalibrationResult
from .train import TrainedModel

ARTIFACT_SCHEMA_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


from god.persist.atomic import atomic_write_bytes as _atomic_write_bytes


def _atomic_write_text(path: Path, content: str) -> None:
    _atomic_write_bytes(path, content.encode("utf-8"))


@dataclass
class ArtifactBundle:
    """On-disk champion bundle metadata + paths."""

    model_id: str
    model_version: str
    backend: str
    features_version: str
    feature_names: list[str]
    dataset_hash: str
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    calibration: Optional[dict[str, Any]] = None
    saved_at: str = ""
    artifact_file: str = "model.pkl"
    calibrator_file: str = "calibrator.json"
    schema_version: str = ARTIFACT_SCHEMA_VERSION
    artifact_checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "backend": self.backend,
            "features_version": self.features_version,
            "feature_names": list(self.feature_names),
            "dataset_hash": self.dataset_hash,
            "metrics": dict(self.metrics),
            "metadata": dict(self.metadata),
            "calibration": dict(self.calibration) if self.calibration else None,
            "saved_at": self.saved_at,
            "artifact_file": self.artifact_file,
            "calibrator_file": self.calibrator_file,
            "schema_version": self.schema_version,
            "artifact_checksum": self.artifact_checksum,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ArtifactBundle":
        meta = dict(d.get("metadata") or {})
        schema = str(d.get("schema_version") or meta.get("schema_version") or ARTIFACT_SCHEMA_VERSION)
        checksum = str(d.get("artifact_checksum") or meta.get("artifact_checksum") or "")
        return cls(
            model_id=str(d["model_id"]),
            model_version=str(d["model_version"]),
            backend=str(d.get("backend", "")),
            features_version=str(d.get("features_version", "")),
            feature_names=list(d.get("feature_names") or []),
            dataset_hash=str(d.get("dataset_hash", "")),
            metrics=dict(d.get("metrics") or {}),
            metadata=meta,
            calibration=dict(d["calibration"]) if d.get("calibration") else None,
            saved_at=str(d.get("saved_at", "")),
            artifact_file=str(d.get("artifact_file", "model.pkl")),
            calibrator_file=str(d.get("calibrator_file", "calibrator.json")),
            schema_version=schema,
            artifact_checksum=checksum,
        )


def _model_dir(root: Path, model_id: str, model_version: str) -> Path:
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in model_id)
    safe_ver = "".join(c if c.isalnum() or c in "._-" else "_" for c in model_version)
    d = root / "artifacts" / f"{safe_id}@{safe_ver}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def validate_artifact_bundle(bundle: ArtifactBundle) -> tuple[bool, str]:
    """Validate bundle metadata integrity. Fail-closed on incomplete records."""
    if not bundle.model_id or not str(bundle.model_id).strip():
        return False, "missing_model_id"
    if not bundle.model_version or not str(bundle.model_version).strip():
        return False, "missing_model_version"
    if not bundle.backend:
        return False, "missing_backend"
    if not bundle.feature_names:
        return False, "missing_feature_names"
    if not bundle.dataset_hash:
        return False, "missing_dataset_hash"
    return True, "ok"


def save_trained_model(
    root: Path,
    model: TrainedModel,
    *,
    calibrator: Optional[PlattCalibrator] = None,
    calibration: Optional[CalibrationResult] = None,
    extra_metrics: Optional[dict[str, float]] = None,
) -> ArtifactBundle:
    """Persist model artifact + optional calibrator under registry root (atomic)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    mdir = _model_dir(root, model.model_id, model.model_version)

    if model.backend == "numpy_logit":
        payload = {
            "backend": "numpy_logit",
            "weights": np.asarray(model.artifact["weights"]).tolist(),
            "bias": float(model.artifact.get("bias", 0.0)),
        }
        raw = pickle.dumps(payload, protocol=4)
    else:
        raw = pickle.dumps(model.artifact, protocol=4)

    art_path = mdir / "model.pkl"
    _atomic_write_bytes(art_path, raw)
    checksum = _sha256_bytes(raw)

    cal_meta: Optional[dict[str, Any]] = None
    if calibrator is not None and calibrator.fitted:
        cal_path = mdir / "calibrator.json"
        cal_payload = {"a": calibrator.a, "b": calibrator.b, "fitted": True}
        _atomic_write_text(cal_path, json.dumps(cal_payload, indent=2))
        cal_meta = cal_payload
        if calibration is not None:
            cal_meta = {**cal_meta, **calibration.to_dict()}

    metrics = {**model.metrics, **(extra_metrics or {})}
    meta = dict(model.metadata or {})
    meta["schema_version"] = ARTIFACT_SCHEMA_VERSION
    meta["artifact_checksum"] = checksum

    bundle = ArtifactBundle(
        model_id=model.model_id,
        model_version=model.model_version,
        backend=model.backend,
        features_version=model.features_version,
        feature_names=list(model.feature_names),
        dataset_hash=model.dataset_hash,
        metrics=metrics,
        metadata=meta,
        calibration=cal_meta,
        saved_at=_utc_now(),
        artifact_file="model.pkl",
        calibrator_file="calibrator.json",
        schema_version=ARTIFACT_SCHEMA_VERSION,
        artifact_checksum=checksum,
    )
    _atomic_write_text(mdir / "bundle.json", json.dumps(bundle.to_dict(), indent=2))
    return bundle


def load_trained_model(
    root: Path, model_id: str, model_version: str
) -> tuple[TrainedModel, Optional[PlattCalibrator], ArtifactBundle]:
    """Load model + optional calibrator. Raises FileNotFoundError if missing."""
    root = Path(root)
    mdir = _model_dir(root, model_id, model_version)
    bundle_path = mdir / "bundle.json"
    if not bundle_path.is_file():
        raise FileNotFoundError(f"bundle not found: {bundle_path}")
    bundle = ArtifactBundle.from_dict(json.loads(bundle_path.read_text(encoding="utf-8")))

    art_path = mdir / bundle.artifact_file
    raw = art_path.read_bytes()
    if bundle.artifact_checksum:
        if _sha256_bytes(raw) != bundle.artifact_checksum:
            raise ValueError("artifact_checksum_mismatch")

    data = pickle.loads(raw)
    if bundle.backend == "numpy_logit":
        artifact: Any = {
            "weights": np.asarray(data["weights"], dtype=float),
            "bias": float(data.get("bias", 0.0)),
        }
    else:
        artifact = data

    model = TrainedModel(
        model_id=bundle.model_id,
        model_version=bundle.model_version,
        backend=bundle.backend,
        feature_names=tuple(bundle.feature_names),
        features_version=bundle.features_version,
        dataset_hash=bundle.dataset_hash,
        artifact=artifact,
        metrics=dict(bundle.metrics),
        metadata=dict(bundle.metadata),
    )

    calibrator: Optional[PlattCalibrator] = None
    cal_path = mdir / bundle.calibrator_file
    if cal_path.is_file():
        cal_data = json.loads(cal_path.read_text(encoding="utf-8"))
        if cal_data.get("fitted"):
            calibrator = PlattCalibrator(
                a=float(cal_data.get("a", 1.0)),
                b=float(cal_data.get("b", 0.0)),
                fitted=True,
            )
    return model, calibrator, bundle


def load_trained_model_safe(
    root: Path, model_id: str, model_version: str
) -> tuple[Optional[TrainedModel], Optional[PlattCalibrator], Optional[ArtifactBundle], str]:
    """Fail-closed load. Returns (None, None, None, status) on any corrupt/missing/invalid.

    status: ok | missing | corrupt | invalid_bundle | checksum_mismatch
    """
    try:
        model, calibrator, bundle = load_trained_model(root, model_id, model_version)
    except FileNotFoundError:
        return None, None, None, "missing"
    except ValueError as e:
        if "checksum" in str(e).lower():
            return None, None, None, "checksum_mismatch"
        return None, None, None, "corrupt"
    except (json.JSONDecodeError, pickle.UnpicklingError, KeyError, TypeError, OSError):
        return None, None, None, "corrupt"
    except Exception:
        return None, None, None, "corrupt"

    ok, reason = validate_artifact_bundle(bundle)
    if not ok:
        return None, None, None, "invalid_bundle"

    try:
        if bundle.backend == "numpy_logit":
            w = model.artifact.get("weights")
            if w is None or len(np.asarray(w).shape) == 0:
                return None, None, None, "corrupt"
        elif model.artifact is None:
            return None, None, None, "corrupt"
    except Exception:
        return None, None, None, "corrupt"

    return model, calibrator, bundle, "ok"
