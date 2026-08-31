"""Curiosity models — anomaly is a question, never a trade signal."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AnomalyType(str, Enum):
    VOLATILITY = "VOLATILITY"
    VOLUME = "VOLUME"
    SPREAD = "SPREAD"
    CORRELATION = "CORRELATION"
    EXECUTION_BEHAVIOR = "EXECUTION_BEHAVIOR"
    REGIME_DEVIATION = "REGIME_DEVIATION"
    DATA = "DATA"
    RESIDUAL = "RESIDUAL"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class CuriosityEvent:
    """Something unusual to investigate — not an order."""

    event_id: str
    timestamp: str
    source: str
    anomaly_type: AnomalyType
    severity: Severity
    evidence_refs: tuple[str, ...] = ()
    observation_refs: tuple[str, ...] = ()
    research_trigger: bool = True
    provenance: Optional[dict[str, Any]] = None
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "evidence_refs": list(self.evidence_refs),
            "observation_refs": list(self.observation_refs),
            "research_trigger": self.research_trigger,
            "provenance": dict(self.provenance) if self.provenance else None,
            "description": self.description,
            "metadata": dict(self.metadata),
        }

    def has_trade_payload(self) -> bool:
        """True if structured fields encode trade intent (must stay False)."""
        keys = " ".join(
            [
                self.anomaly_type.value,
                self.severity.value,
                self.source,
                str(list(self.metadata.keys())),
            ]
        ).lower()
        return any(f in keys for f in ("op_buy", "op_sell", "ordersend", "order_side", "lot_size"))


@dataclass
class AnomalyDescriptor:
    anomaly_type: AnomalyType
    severity: Severity
    score: float  # descriptive magnitude, not a trading threshold law
    observation_ref: Optional[str] = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "score": self.score,
            "observation_ref": self.observation_ref,
            "detail": dict(self.detail),
        }
