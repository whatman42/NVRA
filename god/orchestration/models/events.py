"""Cognitive events — evidence only, no operational order payloads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    OBSERVATION = "OBSERVATION"
    CURIOSITY = "CURIOSITY"
    RESEARCH = "RESEARCH"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT = "EXPERIMENT"
    VALIDATION = "VALIDATION"
    STRATEGY = "STRATEGY"
    REALITY_GAP = "REALITY_GAP"
    RCA = "RCA"
    DRIFT = "DRIFT"
    REGIME = "REGIME"
    POLICY = "POLICY"
    CAPITAL_SAFETY = "CAPITAL_SAFETY"
    ANOMALY = "ANOMALY"
    FAILURE = "FAILURE"
    SCHEDULER = "SCHEDULER"
    POISON = "POISON"
    DEAD_LETTER = "DEAD_LETTER"


class FailureClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    CORRUPTION = "CORRUPTION"
    UNKNOWN = "UNKNOWN"


# Operational / order-like keys never allowed in cognitive payload_ref.
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "side",
        "order_side",
        "order_type",
        "quantity",
        "qty",
        "price",
        "symbol_order",
        "client_order_id",
        "exchange_order_id",
        "live",
        "authorize_live",
        "password",
        "secret",
        "api_key",
        "token",
    }
)


def _stable_id(*parts: str) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"evt-{h[:24]}"


@dataclass
class CognitiveEvent:
    event_id: str
    event_type: EventType
    correlation_id: str
    context_id: str
    parent_event_id: Optional[str] = None
    payload_ref: dict[str, Any] = field(default_factory=dict)
    provenance: str = "orchestration"
    sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CognitiveEvent":
        return cls(
            event_id=str(d["event_id"]),
            event_type=EventType(d["event_type"]),
            correlation_id=str(d["correlation_id"]),
            context_id=str(d["context_id"]),
            parent_event_id=d.get("parent_event_id"),
            payload_ref=dict(d.get("payload_ref") or {}),
            provenance=str(d.get("provenance") or "orchestration"),
            sequence=int(d.get("sequence") or 0),
        )


def create_event(
    event_type: EventType,
    *,
    correlation_id: str,
    context_id: str,
    parent_event_id: Optional[str] = None,
    payload_ref: Optional[dict[str, Any]] = None,
    provenance: str = "orchestration",
    sequence: int = 0,
    event_id: Optional[str] = None,
) -> CognitiveEvent:
    payload = dict(payload_ref or {})
    if event_id is None:
        blob = json.dumps(
            {
                "t": event_type.value,
                "c": correlation_id,
                "x": context_id,
                "p": parent_event_id,
                "b": payload,
                "s": sequence,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        event_id = _stable_id(blob)
    return CognitiveEvent(
        event_id=event_id,
        event_type=event_type,
        correlation_id=correlation_id,
        context_id=context_id,
        parent_event_id=parent_event_id,
        payload_ref=payload,
        provenance=provenance,
        sequence=sequence,
    )
