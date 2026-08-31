"""Model registry records and lifecycle statuses."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ModelStatus(Enum):
    CANDIDATE = auto()
    VALIDATED = auto()
    ACTIVE = auto()
    CANARY = auto()
    RETIRED = auto()
    INVALID = auto()


@dataclass(slots=True)
class RegistryEntry:
    model_id: str
    version: str
    algorithm: str
    feature_schema_version: str
    feature_names: tuple[str, ...]
    training_data_hash: str
    metrics: dict[str, float]
    status: ModelStatus
    artifact_path: str
    created_at_ms: int
    activated_at_ms: int | None = None
    training_rows: int = 0
    profile: str = "ULTRA_LITE"
    label_horizon_bars: int = 5
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "algorithm": self.algorithm,
            "feature_schema_version": self.feature_schema_version,
            "feature_names": list(self.feature_names),
            "training_data_hash": self.training_data_hash,
            "metrics": dict(self.metrics),
            "status": self.status.name,
            "artifact_path": self.artifact_path,
            "created_at_ms": self.created_at_ms,
            "activated_at_ms": self.activated_at_ms,
            "training_rows": self.training_rows,
            "profile": self.profile,
            "label_horizon_bars": self.label_horizon_bars,
            "hyperparameters": dict(self.hyperparameters),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegistryEntry:
        return cls(
            model_id=str(data["model_id"]),
            version=str(data["version"]),
            algorithm=str(data["algorithm"]),
            feature_schema_version=str(data["feature_schema_version"]),
            feature_names=tuple(data["feature_names"]),
            training_data_hash=str(data["training_data_hash"]),
            metrics={k: float(v) for k, v in (data.get("metrics") or {}).items()},
            status=ModelStatus[str(data["status"])],
            artifact_path=str(data["artifact_path"]),
            created_at_ms=int(data["created_at_ms"]),
            activated_at_ms=(
                int(data["activated_at_ms"]) if data.get("activated_at_ms") is not None else None
            ),
            training_rows=int(data.get("training_rows") or 0),
            profile=str(data.get("profile") or "ULTRA_LITE"),
            label_horizon_bars=int(data.get("label_horizon_bars") or 5),
            hyperparameters=dict(data.get("hyperparameters") or {}),
            notes=str(data.get("notes") or ""),
        )
