"""Typed, immutable contracts shared across institutional subsystems."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
import hashlib, json, time, uuid

class MessageKind(str, Enum):
    DATA="DATA"; EVENT="EVENT"; COMMAND="COMMAND"; DECISION="DECISION"; CHECKPOINT="CHECKPOINT"

@dataclass(frozen=True)
class Message:
    kind: MessageKind
    topic: str
    payload: Mapping[str, Any]
    correlation_id: str
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    sequence: int = 0
    timestamp_ns: int = field(default_factory=time.time_ns)

    def fingerprint(self)->str:
        raw=json.dumps({"kind":self.kind.value,"topic":self.topic,"payload":dict(self.payload),
                        "correlation_id":self.correlation_id,"sequence":self.sequence},
                       sort_keys=True,separators=(",",":"),default=str).encode()
        return hashlib.sha256(raw).hexdigest()

@dataclass(frozen=True)
class AgentEvidence:
    source: str
    claim: str
    confidence: float
    timestamp_ns: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")

@dataclass(frozen=True)
class DecisionPacket:
    symbol: str
    action: str
    confidence: float
    thesis: str
    evidence: tuple[AgentEvidence,...] = ()
    risks: tuple[str,...] = ()
    invalidation: tuple[str,...] = ()
    horizon: str = "session"
    suggested_size: float = 0.0
    model_versions: tuple[str,...] = ()
    correlation_id: str = ""

    def __post_init__(self):
        if not self.symbol.strip(): raise ValueError("symbol required")
        if self.action not in {"BUY","SELL","HOLD","NO_ACTION"}: raise ValueError("invalid action")
        if not 0.0 <= self.confidence <= 1.0: raise ValueError("confidence must be in [0,1]")
        if self.suggested_size < 0: raise ValueError("suggested_size must be non-negative")
