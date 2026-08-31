"""Research trigger — CuriosityEvent → 4A ResearchEngine (no rewrite)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from god.research.engine import ResearchEngine
from god.research.models import ExperimentOutcome

from .models import CuriosityEvent


@dataclass
class TriggerResult:
    curiosity_event_id: str
    claim_id: Optional[str] = None
    hypothesis_id: Optional[str] = None
    experiment_id: Optional[str] = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "curiosity_event_id": self.curiosity_event_id,
            "claim_id": self.claim_id,
            "hypothesis_id": self.hypothesis_id,
            "experiment_id": self.experiment_id,
            "provenance": dict(self.provenance),
        }


class ResearchTrigger:
    """Bridge curiosity → claim / hypothesis / experiment design."""

    def __init__(self, research: ResearchEngine) -> None:
        self.research = research

    def trigger(self, event: CuriosityEvent) -> TriggerResult:
        if not event.research_trigger:
            return TriggerResult(curiosity_event_id=event.event_id)

        claim_text = (
            f"Curiosity: unusual {event.anomaly_type.value} "
            f"(severity={event.severity.value}) warrants investigation"
        )
        claim = self.research.propose_claim(
            claim_text,
            source=event.source,
            evidence_text=event.description,
            metadata={
                "curiosity_event_id": event.event_id,
                "anomaly_type": event.anomaly_type.value,
            },
            confidence=None,
        )
        if event.provenance:
            # attach provenance note as evidence
            self.research.attach_evidence(
                claim.claim_id,
                summary="curiosity_provenance",
                weight=1.0,
                methodology="curiosity_trigger",
            )

        hyp = self.research.propose_hypothesis(
            f"Investigate cause of {event.anomaly_type.value} anomaly",
            claim_id=claim.claim_id,
            metadata={
                "curiosity_event_id": event.event_id,
                "candidates": {},  # no indicator laws
            },
        )
        exp = self.research.design_experiment(
            name=f"curiosity_{event.anomaly_type.value}_{event.event_id[:8]}",
            hypothesis_id=hyp.hypothesis_id,
            config={
                "curiosity_event_id": event.event_id,
                "anomaly_type": event.anomaly_type.value,
            },
        )
        return TriggerResult(
            curiosity_event_id=event.event_id,
            claim_id=claim.claim_id,
            hypothesis_id=hyp.hypothesis_id,
            experiment_id=exp.experiment_id,
            provenance=dict(event.provenance or {}),
        )
