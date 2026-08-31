"""Model interface — CRYPTO never depends on LightGBM/XGBoost APIs directly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelMetadata:
    model_id: str
    version: str
    algorithm: str
    feature_schema_version: str
    feature_names: tuple[str, ...]
    training_rows: int
    training_data_hash: str
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    created_at_ms: int = 0
    profile: str = "ULTRA_LITE"
    label_horizon_bars: int = 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "algorithm": self.algorithm,
            "feature_schema_version": self.feature_schema_version,
            "feature_names": list(self.feature_names),
            "training_rows": self.training_rows,
            "training_data_hash": self.training_data_hash,
            "hyperparameters": dict(self.hyperparameters),
            "metrics": dict(self.metrics),
            "created_at_ms": self.created_at_ms,
            "profile": self.profile,
            "label_horizon_bars": self.label_horizon_bars,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelMetadata:
        return cls(
            model_id=str(data["model_id"]),
            version=str(data["version"]),
            algorithm=str(data["algorithm"]),
            feature_schema_version=str(data["feature_schema_version"]),
            feature_names=tuple(data["feature_names"]),
            training_rows=int(data["training_rows"]),
            training_data_hash=str(data["training_data_hash"]),
            hyperparameters=dict(data.get("hyperparameters") or {}),
            metrics={k: float(v) for k, v in (data.get("metrics") or {}).items()},
            created_at_ms=int(data.get("created_at_ms") or 0),
            profile=str(data.get("profile") or "ULTRA_LITE"),
            label_horizon_bars=int(data.get("label_horizon_bars") or 5),
        )


class BaseModel(ABC):
    """Interchangeable classifier: DOWN=0, NEUTRAL=1, UP=2."""

    algorithm: str = "base"

    @abstractmethod
    def fit(
        self,
        x: Sequence[Sequence[float]],
        y: Sequence[int],
        *,
        feature_names: Sequence[str],
    ) -> None: ...

    @abstractmethod
    def predict(self, x: Sequence[Sequence[float]]) -> list[int]: ...

    @abstractmethod
    def predict_proba(self, x: Sequence[Sequence[float]]) -> list[tuple[float, float, float]]:
        """Return (p_down, p_neutral, p_up) per row."""

    @abstractmethod
    def save_bytes(self) -> bytes: ...

    @classmethod
    @abstractmethod
    def load_bytes(cls, data: bytes) -> BaseModel: ...

    def metadata(self) -> dict[str, Any]:
        return {"algorithm": self.algorithm}
