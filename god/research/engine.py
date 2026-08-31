"""ResearchEngine — orchestrates discovery → claim → hypothesis → experiment.

Does not execute trades. Does not unlock production execution.
Integrates with frozen MemoryStore (audit, knowledge, hypothesis, experience).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence
from uuid import uuid4

from god.memory.database import utc_now
from god.memory.models import (
    AuditRecord,
    Experience,
    Hypothesis,
    KnowledgeClaim,
)
from god.memory.repositories import MemoryStore

from .anomaly import AnomalyDetector, AnomalyReport
from .assessment import assess_evidence
from .models import (
    AssessmentResult,
    ClaimStatus,
    EvidenceRecord,
    ExperimentOutcome,
    FactRecord,
    HypothesisStatus,
    ProvenanceRecord,
    SourceReliability,
)
from .provenance import build_provenance, content_hash
from .registry import ExperimentRegistry
from .sources import SourceTracker


class ResearchEngine:
    """Additive research brain foundation (Phase 4A)."""

    COMPONENT = "research"

    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self.sources = SourceTracker()
        self.anomaly = AnomalyDetector()
        self.registry = ExperimentRegistry(store)
        self._facts: dict[str, FactRecord] = {}
        self._evidence: dict[str, list[EvidenceRecord]] = {}
        self._provenance: dict[str, ProvenanceRecord] = {}

    # ── DATA / PROVENANCE ─────────────────────────────────────────────

    def ingest_data(
        self,
        payload: str | dict | list,
        *,
        origin: str,
        source_name: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> tuple[ProvenanceRecord, AnomalyReport]:
        source = None
        if source_name or source_id:
            source = self.sources.register(source_name or "unnamed", source_id=source_id)
        prov = build_provenance(
            origin=origin,
            payload=payload,
            source_id=source.source_id if source else None,
        )
        self._provenance[prov.provenance_id] = prov
        report = self.anomaly.inspect(payload, source=source, provenance=prov)
        if report.anomalous and source:
            self.sources.record_anomaly(source.source_id)
            self._audit(
                "anomaly_detected",
                "provenance",
                prov.provenance_id,
                evidence={"reasons": report.reasons, "content_hash": report.content_hash},
            )
        elif source:
            self.sources.record_success(source.source_id)
        self._audit(
            "data_ingested",
            "provenance",
            prov.provenance_id,
            new_state=prov.to_dict(),
        )
        return prov, report

    def record_fact(
        self,
        statement: str,
        *,
        provenance_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> FactRecord:
        fact = FactRecord(
            fact_id=str(uuid4()),
            statement=statement,
            observed_at=utc_now(),
            provenance_id=provenance_id,
            content_hash=content_hash(statement),
            metadata=dict(metadata or {}),
        )
        self._facts[fact.fact_id] = fact
        self._audit("fact_recorded", "fact", fact.fact_id, new_state=fact.to_dict())
        return fact

    # ── RESEARCH / CLAIM ──────────────────────────────────────────────

    def propose_claim(
        self,
        claim_text: str,
        *,
        source: Optional[str] = None,
        url: Optional[str] = None,
        evidence_text: Optional[str] = None,
        methodology: Optional[str] = None,
        limitations: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> KnowledgeClaim:
        """Persist a claim — not yet a law. Confidence is optional metadata."""
        k = KnowledgeClaim.create(
            claim_text,
            source=source,
            url=url,
            evidence=evidence_text,
            methodology=methodology,
            limitations=limitations,
            confidence=confidence,
            status=ClaimStatus.DISCOVERED.value,
            metadata=metadata or {},
            content_hash=content_hash(claim_text),
        )
        self.store.upsert_knowledge(k)
        self._audit("claim_proposed", "knowledge_claim", k.claim_id, new_state={"claim": claim_text})
        return k

    def attach_evidence(
        self,
        claim_id: str,
        summary: str,
        *,
        fact_ids: Optional[Sequence[str]] = None,
        weight: float = 1.0,
        methodology: Optional[str] = None,
        limitations: Optional[str] = None,
    ) -> EvidenceRecord:
        ev = EvidenceRecord(
            evidence_id=str(uuid4()),
            claim_id=claim_id,
            summary=summary,
            fact_ids=list(fact_ids or []),
            weight=weight,
            methodology=methodology,
            limitations=limitations,
            created_at=utc_now(),
        )
        self._evidence.setdefault(claim_id, []).append(ev)
        self._audit("evidence_attached", "evidence", ev.evidence_id, new_state=ev.to_dict())
        return ev

    def assess_claim(
        self,
        claim_id: str,
        *,
        source_id: Optional[str] = None,
        contradicting: int = 0,
    ) -> AssessmentResult:
        evidence = self._evidence.get(claim_id, [])
        source = self.sources.get(source_id) if source_id else None
        result = assess_evidence(
            claim_id, evidence, source=source, contradicting=contradicting
        )
        self._audit(
            "claim_assessed",
            "knowledge_claim",
            claim_id,
            evidence=result.to_dict(),
        )
        return result

    # ── HYPOTHESIS ────────────────────────────────────────────────────

    def propose_hypothesis(
        self,
        statement: str,
        *,
        claim_id: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> Hypothesis:
        """Hypothesis may encode candidate parameters (e.g. indicator names)
        but those are experimental variables — never system law.
        """
        h = Hypothesis.create(
            statement,
            claim_id=claim_id,
            confidence=confidence,
            status=HypothesisStatus.PROPOSED.value,
            metadata=metadata or {},
        )
        self.store.upsert_hypothesis(h)
        self._audit(
            "hypothesis_proposed",
            "hypothesis",
            h.hypothesis_id,
            new_state={"statement": statement, "metadata": h.metadata},
        )
        return h

    # ── EXPERIMENT ────────────────────────────────────────────────────

    def design_experiment(
        self,
        name: str,
        *,
        hypothesis_id: Optional[str] = None,
        config: Optional[dict] = None,
        priority: float = 0.0,
    ):
        exp = self.registry.register(
            name, hypothesis_id=hypothesis_id, config=config, priority=priority
        )
        if hypothesis_id:
            h = Hypothesis.create(
                statement="",  # will not overwrite statement without load API
                hypothesis_id=hypothesis_id,
                experiment_id=exp.experiment_id,
                status=HypothesisStatus.TESTING.value,
            )
            # Only update linkage fields via upsert if we have statement — skip blank overwrite
            # Link via audit for Phase 4A; full hypothesis reload is 4B territory
            self._audit(
                "experiment_designed",
                "experiment",
                exp.experiment_id,
                new_state={"hypothesis_id": hypothesis_id, "config": config or {}},
            )
        else:
            self._audit(
                "experiment_designed",
                "experiment",
                exp.experiment_id,
                new_state={"config": config or {}},
            )
        return exp

    def run_experiment_record(
        self,
        experiment_id: str,
        *,
        outcome: ExperimentOutcome,
        metrics: Optional[dict] = None,
        notes: Optional[str] = None,
    ):
        """Record experiment outcome (caller supplies evaluation — no built-in strategy)."""
        self.registry.start(experiment_id)
        result = self.registry.complete(
            experiment_id, outcome=outcome, metrics=metrics, notes=notes
        )
        self._audit(
            "experiment_completed",
            "experiment",
            experiment_id,
            evidence={"outcome": outcome.value, "metrics": metrics or {}, "notes": notes},
        )
        if outcome == ExperimentOutcome.FAIL:
            self._audit(
                "experiment_failed",
                "experiment",
                experiment_id,
                reason=notes or "FAIL",
                evidence={"metrics": metrics or {}},
            )
        return result

    def record_experience(
        self,
        summary: str,
        *,
        kind: str = "research",
        metadata: Optional[dict] = None,
    ) -> Experience:
        # Experience is a frozen Phase-2 shape (market/trade oriented).
        # Research notes live in market_state / features — not as strategy rules.
        exp = Experience.create(
            outcome=kind,
            market_state={"summary": summary, "domain": "research"},
            features=dict(metadata or {}),
            is_virtual=True,
        )
        self.store.add_experience(exp)
        self._audit(
            "experience_recorded",
            "experience",
            exp.experience_id,
            new_state={"summary": summary, "kind": kind},
        )
        return exp

    def failed_experiments(self):
        return self.registry.list_failed()

    def is_source_quarantined(self, source_id: str) -> bool:
        p = self.sources.get(source_id)
        return bool(p and p.reliability == SourceReliability.QUARANTINED)

    def _audit(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        *,
        old_state: Optional[dict] = None,
        new_state: Optional[dict] = None,
        reason: Optional[str] = None,
        evidence: Optional[dict] = None,
    ) -> None:
        rec = AuditRecord.create(
            component=self.COMPONENT,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_state=old_state,
            new_state=new_state,
            reason=reason,
            evidence=evidence,
            actor="research_engine",
        )
        self.store.append_audit(rec)

