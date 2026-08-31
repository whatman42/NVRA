"""Phase 4C — Research-layer Strategy as versioned artifact.

Strategy is NOT a BUY/SELL function and has ZERO capital authority.
All fields are research/intelligence metadata only.
Execution remains Null/Virtual. No LIVE execution-enabled state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now
from god.research.provenance import content_hash, build_provenance


class LifecycleState(str, Enum):
    """Research lifecycle states. No LIVE / real-execution state."""

    CANDIDATE = "CANDIDATE"
    EXPERIMENTAL = "EXPERIMENTAL"
    VALIDATING = "VALIDATING"
    PAPER = "PAPER"
    PROBATION = "PROBATION"
    DEGRADED = "DEGRADED"
    RECOVERY = "RECOVERY"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"  # still execution-LOCKED


class MutationType(str, Enum):
    PARAMETER_MUTATION = "PARAMETER_MUTATION"
    FEATURE_MUTATION = "FEATURE_MUTATION"
    RULE_STRUCTURE_MUTATION = "RULE_STRUCTURE_MUTATION"
    HORIZON_MUTATION = "HORIZON_MUTATION"
    FILTER_MUTATION = "FILTER_MUTATION"
    ENSEMBLE_MUTATION = "ENSEMBLE_MUTATION"
    OTHER = "OTHER"


@dataclass(frozen=True)
class TransitionRecord:
    """Auditable, deterministic state transition."""

    transition_id: str
    strategy_id: str
    version: int
    from_state: LifecycleState
    to_state: LifecycleState
    reason: str
    evidence_refs: tuple[str, ...] = ()
    actor: str = "system"
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "strategy_id": self.strategy_id,
            "version": self.version,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "actor": self.actor,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MutationRecord:
    """Immutable record of a controlled mutation producing a new version."""

    mutation_id: str
    parent_strategy_id: str
    parent_version: int
    child_strategy_id: str
    child_version: int
    mutation_type: MutationType
    changes: dict[str, Any]  # old → new parameter map
    seed: Optional[int] = None
    timestamp: str = ""
    provenance: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "parent_strategy_id": self.parent_strategy_id,
            "parent_version": self.parent_version,
            "child_strategy_id": self.child_strategy_id,
            "child_version": self.child_version,
            "mutation_type": self.mutation_type.value,
            "changes": dict(self.changes),
            "seed": self.seed,
            "timestamp": self.timestamp,
            "provenance": dict(self.provenance) if self.provenance else None,
            "metadata": dict(self.metadata),
        }


@dataclass
class ResearchStrategy:
    """Versioned research artifact. Immutable historical versions.

    Identity + lineage + evidence only. No order payload, no broker access,
    no capital allocation fields.
    """

    strategy_id: str
    name: str
    version: int = 1
    lifecycle_state: LifecycleState = LifecycleState.CANDIDATE
    parent_strategy_id: Optional[str] = None
    parent_version: Optional[int] = None
    hypothesis_ref: Optional[str] = None
    experiment_refs: list[str] = field(default_factory=list)
    dataset_refs: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    methodology: Optional[str] = None
    provenance: Optional[dict[str, Any]] = None
    validation_metadata: dict[str, Any] = field(default_factory=dict)
    performance_observations: dict[str, Any] = field(default_factory=dict)
    mutation_history: list[str] = field(default_factory=list)  # mutation_ids
    retirement_reason: Optional[str] = None
    retirement_evidence: list[str] = field(default_factory=list)
    replacement_strategy_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def create(
        name: str,
        *,
        parameters: Optional[dict] = None,
        hypothesis_ref: Optional[str] = None,
        experiment_refs: Optional[list[str]] = None,
        dataset_refs: Optional[list[str]] = None,
        assumptions: Optional[list[str]] = None,
        methodology: Optional[str] = None,
        parent_strategy_id: Optional[str] = None,
        parent_version: Optional[int] = None,
        version: int = 1,
        lifecycle_state: LifecycleState = LifecycleState.CANDIDATE,
        actor: str = "research",
        **kw: Any,
    ) -> "ResearchStrategy":
        now = utc_now()
        sid = kw.get("strategy_id") or str(uuid4())
        params = dict(parameters or {})
        payload = {
            "name": name,
            "version": version,
            "parameters": params,
            "hypothesis_ref": hypothesis_ref,
            "parent_strategy_id": parent_strategy_id,
            "parent_version": parent_version,
        }
        prov = build_provenance(
            origin=f"strategy:{actor}",
            payload=payload,
            metadata={"strategy_id": sid, "name": name},
        )
        return ResearchStrategy(
            strategy_id=sid,
            name=name,
            version=version,
            lifecycle_state=lifecycle_state,
            parent_strategy_id=parent_strategy_id,
            parent_version=parent_version,
            hypothesis_ref=hypothesis_ref,
            experiment_refs=list(experiment_refs or []),
            dataset_refs=list(dataset_refs or []),
            parameters=params,
            assumptions=list(assumptions or []),
            methodology=methodology,
            provenance=prov.to_dict() if hasattr(prov, "to_dict") else {
                "provenance_id": prov.provenance_id,
                "origin": prov.origin,
                "content_hash": prov.content_hash,
                "retrieved_at": prov.retrieved_at,
            },
            created_at=kw.get("created_at", now),
            updated_at=kw.get("updated_at", now),
            content_hash=content_hash(payload),
            metadata=dict(kw.get("metadata") or {}),
        )

    def identity_key(self) -> str:
        return f"{self.strategy_id}:v{self.version}"

    def has_trade_payload(self) -> bool:
        """Must remain False — strategy is research only."""
        blob = " ".join(
            [
                self.name,
                str(self.parameters.keys()),
                str(self.metadata.keys()),
                str(self.assumptions),
            ]
        ).lower()
        forbidden = (
            "op_buy",
            "op_sell",
            "ordersend",
            "order_side",
            "lot_size",
            "broker_credential",
            "api_key",
            "telegram_token",
            "gh_pat",
        )
        return any(f in blob for f in forbidden)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "version": self.version,
            "lifecycle_state": self.lifecycle_state.value,
            "parent_strategy_id": self.parent_strategy_id,
            "parent_version": self.parent_version,
            "hypothesis_ref": self.hypothesis_ref,
            "experiment_refs": list(self.experiment_refs),
            "dataset_refs": list(self.dataset_refs),
            "parameters": dict(self.parameters),
            "assumptions": list(self.assumptions),
            "methodology": self.methodology,
            "provenance": dict(self.provenance) if self.provenance else None,
            "validation_metadata": dict(self.validation_metadata),
            "performance_observations": dict(self.performance_observations),
            "mutation_history": list(self.mutation_history),
            "retirement_reason": self.retirement_reason,
            "retirement_evidence": list(self.retirement_evidence),
            "replacement_strategy_id": self.replacement_strategy_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "content_hash": self.content_hash,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ResearchStrategy":
        return ResearchStrategy(
            strategy_id=d["strategy_id"],
            name=d["name"],
            version=int(d.get("version", 1)),
            lifecycle_state=LifecycleState(d.get("lifecycle_state", "CANDIDATE")),
            parent_strategy_id=d.get("parent_strategy_id"),
            parent_version=d.get("parent_version"),
            hypothesis_ref=d.get("hypothesis_ref"),
            experiment_refs=list(d.get("experiment_refs") or []),
            dataset_refs=list(d.get("dataset_refs") or []),
            parameters=dict(d.get("parameters") or {}),
            assumptions=list(d.get("assumptions") or []),
            methodology=d.get("methodology"),
            provenance=d.get("provenance"),
            validation_metadata=dict(d.get("validation_metadata") or {}),
            performance_observations=dict(d.get("performance_observations") or {}),
            mutation_history=list(d.get("mutation_history") or []),
            retirement_reason=d.get("retirement_reason"),
            retirement_evidence=list(d.get("retirement_evidence") or []),
            replacement_strategy_id=d.get("replacement_strategy_id"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            content_hash=d.get("content_hash"),
            metadata=dict(d.get("metadata") or {}),
        )


@dataclass
class ComparisonEvidence:
    """Comparison result is evidence, never an automatic live winner."""

    comparison_id: str
    strategy_a_id: str
    strategy_a_version: int
    strategy_b_id: str
    strategy_b_version: int
    baseline_id: Optional[str] = None
    observations: dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None
    timestamp: str = ""
    provenance: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "strategy_a_id": self.strategy_a_id,
            "strategy_a_version": self.strategy_a_version,
            "strategy_b_id": self.strategy_b_id,
            "strategy_b_version": self.strategy_b_version,
            "baseline_id": self.baseline_id,
            "observations": dict(self.observations),
            "notes": self.notes,
            "timestamp": self.timestamp,
            "provenance": dict(self.provenance) if self.provenance else None,
        }
