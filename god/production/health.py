"""Phase 6A — N.U.N.G. production foundation health. Fail-closed."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import ProductionConfig
from .validation import ConfigValidationResult, ConfigValidationStatus, validate_config


class ProductionHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProductionHealth:
    state: ProductionHealthState
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"state": self.state.value, "reasons": list(self.reasons)}


def assess_health(
    config: Optional[ProductionConfig] = None,
    validation: Optional[ConfigValidationResult] = None,
) -> ProductionHealth:
    if config is None:
        return ProductionHealth(ProductionHealthState.UNKNOWN, ("missing_config",))
    validation = validation or validate_config(config)
    if validation.status == ConfigValidationStatus.VALID:
        return ProductionHealth(ProductionHealthState.HEALTHY, ())
    if validation.status == ConfigValidationStatus.BLOCKED:
        return ProductionHealth(ProductionHealthState.BLOCKED, validation.reasons)
    if validation.status == ConfigValidationStatus.INVALID:
        return ProductionHealth(ProductionHealthState.INVALID, validation.reasons)
    return ProductionHealth(ProductionHealthState.UNKNOWN, validation.reasons)
