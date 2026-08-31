"""Typed domain models for persistent memory (research/audit entities).

Pure data containers — no trading logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .models_core import new_id

@dataclass
class Experiment:
    experiment_id: str
    name: str
    status: str = "PENDING"
    hypothesis_id: Optional[str] = None
    priority: float = 0.0
    config: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    @staticmethod
    def create(name: str, **kw: Any) -> "Experiment":
        from .database import utc_now
        now = utc_now()
        return Experiment(
            experiment_id=kw.get("experiment_id") or new_id(),
            name=name, status=kw.get("status", "PENDING"),
            hypothesis_id=kw.get("hypothesis_id"),
            priority=kw.get("priority", 0.0),
            config=kw.get("config") or {},
            created_at=kw.get("created_at", now),
            updated_at=kw.get("updated_at", now),
            started_at=kw.get("started_at"), finished_at=kw.get("finished_at"),
        )


@dataclass
class ExperimentResult:
    result_id: str
    experiment_id: str
    metrics: dict = field(default_factory=dict)
    passed: Optional[bool] = None
    notes: Optional[str] = None
    created_at: str = ""

    @staticmethod
    def create(experiment_id: str, **kw: Any) -> "ExperimentResult":
        from .database import utc_now
        return ExperimentResult(
            result_id=kw.get("result_id") or new_id(),
            experiment_id=experiment_id,
            metrics=kw.get("metrics") or {},
            passed=kw.get("passed"),
            notes=kw.get("notes"),
            created_at=kw.get("created_at", utc_now()),
        )


@dataclass
class KnowledgeClaim:
    claim_id: str
    claim: str
    retrieval_date: str
    source: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    publication_date: Optional[str] = None
    content_hash: Optional[str] = None
    evidence: Optional[str] = None
    methodology: Optional[str] = None
    dataset: Optional[str] = None
    limitations: Optional[str] = None
    confidence: Optional[float] = None
    status: str = "DISCOVERED"
    validation_status: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def create(claim: str, **kw: Any) -> "KnowledgeClaim":
        from .database import utc_now
        now = utc_now()
        return KnowledgeClaim(
            claim_id=kw.get("claim_id") or new_id(),
            claim=claim,
            retrieval_date=kw.get("retrieval_date", now),
            source=kw.get("source"), url=kw.get("url"), title=kw.get("title"),
            author=kw.get("author"), publication_date=kw.get("publication_date"),
            content_hash=kw.get("content_hash"), evidence=kw.get("evidence"),
            methodology=kw.get("methodology"), dataset=kw.get("dataset"),
            limitations=kw.get("limitations"), confidence=kw.get("confidence"),
            status=kw.get("status", "DISCOVERED"),
            validation_status=kw.get("validation_status"),
            metadata=kw.get("metadata") or {},
            created_at=kw.get("created_at", now),
            updated_at=kw.get("updated_at", now),
        )


@dataclass
class Hypothesis:
    hypothesis_id: str
    statement: str
    status: str = "PROPOSED"
    claim_id: Optional[str] = None
    confidence: Optional[float] = None
    experiment_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def create(statement: str, **kw: Any) -> "Hypothesis":
        from .database import utc_now
        now = utc_now()
        return Hypothesis(
            hypothesis_id=kw.get("hypothesis_id") or new_id(),
            statement=statement,
            status=kw.get("status", "PROPOSED"),
            claim_id=kw.get("claim_id"),
            confidence=kw.get("confidence"),
            experiment_id=kw.get("experiment_id"),
            created_at=kw.get("created_at", now),
            updated_at=kw.get("updated_at", now),
            metadata=kw.get("metadata") or {},
        )


@dataclass
class RiskEvent:
    event_id: str
    timestamp: str
    event_type: str
    severity: str = "info"
    symbol: Optional[str] = None
    details: dict = field(default_factory=dict)
    created_at: str = ""

    @staticmethod
    def create(event_type: str, **kw: Any) -> "RiskEvent":
        from .database import utc_now
        now = utc_now()
        return RiskEvent(
            event_id=kw.get("event_id") or new_id(),
            timestamp=kw.get("timestamp", now),
            event_type=event_type,
            severity=kw.get("severity", "info"),
            symbol=kw.get("symbol"),
            details=kw.get("details") or {},
            created_at=kw.get("created_at", now),
        )


@dataclass
class CapabilityEvent:
    event_id: str
    timestamp: str
    event_type: str
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    capability: Optional[str] = None
    details: dict = field(default_factory=dict)
    created_at: str = ""

    @staticmethod
    def create(event_type: str, **kw: Any) -> "CapabilityEvent":
        from .database import utc_now
        now = utc_now()
        return CapabilityEvent(
            event_id=kw.get("event_id") or new_id(),
            timestamp=kw.get("timestamp", now),
            event_type=event_type,
            provider_id=kw.get("provider_id"),
            provider_name=kw.get("provider_name"),
            capability=kw.get("capability"),
            details=kw.get("details") or {},
            created_at=kw.get("created_at", now),
        )


@dataclass
class AuditRecord:
    audit_id: str
    timestamp: str
    component: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    old_state: Optional[dict] = None
    new_state: Optional[dict] = None
    reason: Optional[str] = None
    evidence: Optional[dict] = None
    actor: str = "agent"
    created_at: str = ""

    @staticmethod
    def create(component: str, action: str, **kw: Any) -> "AuditRecord":
        from .database import utc_now
        now = utc_now()
        return AuditRecord(
            audit_id=kw.get("audit_id") or new_id(),
            timestamp=kw.get("timestamp", now),
            component=component, action=action,
            entity_type=kw.get("entity_type"),
            entity_id=kw.get("entity_id"),
            old_state=kw.get("old_state"),
            new_state=kw.get("new_state"),
            reason=kw.get("reason"),
            evidence=kw.get("evidence"),
            actor=kw.get("actor", "agent"),
            created_at=kw.get("created_at", now),
        )


@dataclass
class AgentState:
    key: str
    value: Any
    updated_at: str = ""

    @staticmethod
    def create(key: str, value: Any) -> "AgentState":
        from .database import utc_now
        return AgentState(key=key, value=value, updated_at=utc_now())


@dataclass
class ModelArtifact:
    artifact_id: str
    name: str
    version: str
    artifact_type: str
    path: Optional[str] = None
    checksum: Optional[str] = None
    metrics: dict = field(default_factory=dict)
    status: str = "CANDIDATE"
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def create(name: str, version: str, artifact_type: str, **kw: Any) -> "ModelArtifact":
        from .database import utc_now
        now = utc_now()
        return ModelArtifact(
            artifact_id=kw.get("artifact_id") or new_id(),
            name=name, version=version, artifact_type=artifact_type,
            path=kw.get("path"), checksum=kw.get("checksum"),
            metrics=kw.get("metrics") or {},
            status=kw.get("status", "CANDIDATE"),
            created_at=kw.get("created_at", now),
            updated_at=kw.get("updated_at", now),
        )
