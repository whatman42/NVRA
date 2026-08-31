"""Dataset governance — immutable training snapshots, versioning, leakage guards."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import numpy as np

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _stable_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:32]

@dataclass
class DatasetSnapshot:
    dataset_version: str
    feature_schema_version: str
    label_version: str
    n_samples: int
    n_features: int
    timestamp_start: str = ""
    timestamp_end: str = ""
    source: str = ""
    class_distribution: dict[str, int] = field(default_factory=dict)
    regime_distribution: dict[str, int] = field(default_factory=dict)
    checksum: str = ""
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    chronological: bool = True
    purge_embargo: int = 0
    calibration_held_out: bool = True
    oos_unseen: bool = True
    valid: bool = True
    reason: str = "ok"
    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "feature_schema_version": self.feature_schema_version,
            "label_version": self.label_version,
            "n_samples": self.n_samples,
            "n_features": self.n_features,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "source": self.source,
            "class_distribution": dict(self.class_distribution),
            "regime_distribution": dict(self.regime_distribution),
            "checksum": self.checksum,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
            "chronological": self.chronological,
            "purge_embargo": self.purge_embargo,
            "calibration_held_out": self.calibration_held_out,
            "oos_unseen": self.oos_unseen,
            "valid": self.valid,
            "reason": self.reason,
        }
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DatasetSnapshot":
        return cls(
            dataset_version=str(d.get("dataset_version", "")),
            feature_schema_version=str(d.get("feature_schema_version", "")),
            label_version=str(d.get("label_version", "")),
            n_samples=int(d.get("n_samples", 0)),
            n_features=int(d.get("n_features", 0)),
            timestamp_start=str(d.get("timestamp_start", "")),
            timestamp_end=str(d.get("timestamp_end", "")),
            source=str(d.get("source", "")),
            class_distribution={str(k): int(v) for k, v in (d.get("class_distribution") or {}).items()},
            regime_distribution={str(k): int(v) for k, v in (d.get("regime_distribution") or {}).items()},
            checksum=str(d.get("checksum", "")),
            created_at=str(d.get("created_at", "")),
            metadata=dict(d.get("metadata") or {}),
            chronological=bool(d.get("chronological", True)),
            purge_embargo=int(d.get("purge_embargo", 0)),
            calibration_held_out=bool(d.get("calibration_held_out", True)),
            oos_unseen=bool(d.get("oos_unseen", True)),
            valid=bool(d.get("valid", True)),
            reason=str(d.get("reason", "ok")),
        )

def compute_matrix_checksum(X: np.ndarray, y: np.ndarray) -> str:
    x = np.asarray(X, dtype=np.float32)
    yy = np.asarray(y, dtype=np.float32).reshape(-1)
    return _stable_hash(x.tobytes() + yy.tobytes() + f"{x.shape}:{yy.shape}".encode())

def class_counts(y: np.ndarray) -> dict[str, int]:
    y = np.asarray(y).astype(int).ravel()
    vals, counts = np.unique(y, return_counts=True)
    return {str(int(v)): int(c) for v, c in zip(vals, counts)}

def build_dataset_snapshot(X, y, *, feature_schema_version="v1", label_version="direction_v1", dataset_version="", source="bars", regime_labels=None, purge_embargo=1, min_samples=30, min_features=1, metadata=None):
    X, y = np.asarray(X), np.asarray(y).ravel()
    n, nf = (int(X.shape[0]), int(X.shape[1])) if X.ndim == 2 else (0, 0)
    if n < min_samples or nf < min_features or len(y) != n:
        return DatasetSnapshot(dataset_version=dataset_version or "invalid", feature_schema_version=feature_schema_version, label_version=label_version, n_samples=n, n_features=nf, valid=False, reason="insufficient_or_shape_mismatch", created_at=_utc_now(), purge_embargo=purge_embargo, metadata=dict(metadata or {}))
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        return DatasetSnapshot(dataset_version=dataset_version or "invalid", feature_schema_version=feature_schema_version, label_version=label_version, n_samples=n, n_features=nf, valid=False, reason="non_finite_values", created_at=_utc_now(), purge_embargo=purge_embargo, metadata=dict(metadata or {}))
    checksum = compute_matrix_checksum(X, y)
    regime_dist = {}
    if regime_labels is not None and len(regime_labels) == n:
        for r in np.asarray(regime_labels).astype(str):
            regime_dist[r] = regime_dist.get(r, 0) + 1
    return DatasetSnapshot(dataset_version=dataset_version or f"ds_{checksum[:12]}", feature_schema_version=feature_schema_version, label_version=label_version, n_samples=n, n_features=nf, source=source, class_distribution=class_counts(y), regime_distribution=regime_dist, checksum=checksum, created_at=_utc_now(), metadata=dict(metadata or {}), chronological=True, purge_embargo=purge_embargo, calibration_held_out=True, oos_unseen=True, valid=True, reason="ok")

def detect_leakage(train_idx, test_idx, *, embargo=1):
    train_idx, test_idx = np.asarray(train_idx, dtype=int), np.asarray(test_idx, dtype=int)
    if len(train_idx) == 0 or len(test_idx) == 0: return False, "empty_split"
    if np.intersect1d(train_idx, test_idx).size > 0: return False, "train_test_overlap"
    if int(test_idx.min()) <= int(train_idx.max()): return False, "test_before_or_inside_train"
    gap = int(test_idx.min()) - int(train_idx.max()) - 1
    if gap < embargo: return False, f"embargo_violated_gap={gap}_need={embargo}"
    return True, "ok"



def validate_snapshot(snap, *, min_samples=30):
    if not snap.valid: return False, snap.reason
    if snap.n_samples < min_samples: return False, "n_samples_below_min"
    if not snap.checksum: return False, "missing_checksum"
    if not snap.chronological: return False, "not_chronological"
    return True, "ok"
