"""Failure RCA Engine — multi-cause, epistemic status, deterministic, idempotent.

Produces RootCauseAssessment. Never auto-retires strategies. Never executes.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now
from god.research.provenance import build_provenance

from .evidence import require_evidence_for_confirmation
from .models import (
    CauseHypothesis,
    FailureEvent,
    FailureSeverity,
    FailureStatus,
    RootCauseAssessment,
    make_assessment_id,
    make_failure_id,
)
from .taxonomy import CausalStatus, CauseCategory, CauseRole


class RCAEngine:
    def __init__(self) -> None:
        self._failures: dict[str, FailureEvent] = {}
        self._assessments: dict[str, RootCauseAssessment] = {}

    def record_failure(
        self,
        *,
        source: str,
        expected_behavior: Optional[str] = None,
        observed_behavior: Optional[str] = None,
        strategy_ref: Optional[str] = None,
        strategy_version: Optional[int] = None,
        experiment_ref: Optional[str] = None,
        severity: FailureSeverity = FailureSeverity.UNKNOWN,
        evidence_refs: Optional[list[str]] = None,
        gap_refs: Optional[list[str]] = None,
        notes: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> FailureEvent:
        fid = make_failure_id(
            source, strategy_ref, experiment_ref, expected_behavior, observed_behavior
        )
        if fid in self._failures:
            return self._failures[fid]

        prov = build_provenance(
            origin="failure_event",
            payload={
                "failure_id": fid,
                "source": source,
                "expected": expected_behavior,
                "observed": observed_behavior,
            },
        )
        ev = FailureEvent(
            failure_id=fid,
            timestamp=utc_now(),
            source=source,
            strategy_ref=strategy_ref,
            strategy_version=strategy_version,
            experiment_ref=experiment_ref,
            expected_behavior=expected_behavior,
            observed_behavior=observed_behavior,
            severity=severity,
            evidence_refs=list(evidence_refs or []),
            gap_refs=list(gap_refs or []),
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            status=FailureStatus.OPEN,
            notes=notes,
            metadata=dict(metadata or {}),
        )
        self._failures[fid] = ev
        return ev

    def add_cause(
        self,
        failure: FailureEvent,
        *,
        category: CauseCategory,
        role: CauseRole = CauseRole.CANDIDATE_ROOT_CAUSE,
        causal_status: CausalStatus = CausalStatus.HYPOTHESIZED,
        description: str = "",
        evidence_refs: Optional[list[str]] = None,
        descriptive_weight: Optional[float] = None,
    ) -> CauseHypothesis:
        if causal_status == CausalStatus.CONFIRMED and not (evidence_refs or []):
            raise ValueError("CONFIRMED cause requires non-empty evidence_refs")
        cause = CauseHypothesis(
            cause_id=str(uuid4()),
            category=category,
            role=role,
            causal_status=causal_status,
            description=description,
            evidence_refs=tuple(evidence_refs or ()),
            descriptive_weight=descriptive_weight,
        )
        if not require_evidence_for_confirmation(cause):
            raise ValueError("invalid confirmation without evidence")
        failure.candidate_causes = list(failure.candidate_causes) + [cause]
        failure.status = FailureStatus.UNDER_ANALYSIS
        self._failures[failure.failure_id] = failure
        return cause

    def assess(
        self,
        failure: FailureEvent,
        *,
        primary: Optional[CauseHypothesis] = None,
        contributing: Optional[list[CauseHypothesis]] = None,
        overall_status: Optional[CausalStatus] = None,
        conclusion: str = "",
        lifecycle_evidence_hint: Optional[str] = None,
        extra_evidence_refs: Optional[list[str]] = None,
    ) -> RootCauseAssessment:
        """Produce assessment. Idempotent on (failure_id, evidence fingerprint)."""
        causes = list(failure.candidate_causes)
        if primary is None and causes:
            # pick first CONFIRMED else first CANDIDATE else None
            confirmed = [
                c
                for c in causes
                if c.role == CauseRole.CONFIRMED_ROOT_CAUSE
                and c.causal_status == CausalStatus.CONFIRMED
            ]
            candidates = [
                c for c in causes if c.role == CauseRole.CANDIDATE_ROOT_CAUSE
            ]
            primary = confirmed[0] if confirmed else (candidates[0] if candidates else None)

        contrib = contributing if contributing is not None else [
            c
            for c in causes
            if c.role == CauseRole.CONTRIBUTING_FACTOR
            or (
                primary is not None
                and c.cause_id != primary.cause_id
                and c.role
                in (CauseRole.CANDIDATE_ROOT_CAUSE, CauseRole.CONTRIBUTING_FACTOR)
            )
        ]

        if overall_status is None:
            if primary and primary.causal_status == CausalStatus.CONFIRMED:
                overall_status = CausalStatus.CONFIRMED
            elif primary and primary.causal_status == CausalStatus.HYPOTHESIZED:
                overall_status = CausalStatus.HYPOTHESIZED
            elif primary and primary.causal_status == CausalStatus.INFERRED:
                overall_status = CausalStatus.INFERRED
            elif not causes:
                overall_status = CausalStatus.UNKNOWN
            else:
                overall_status = CausalStatus.INSUFFICIENT_EVIDENCE

        if not conclusion:
            if overall_status == CausalStatus.UNKNOWN:
                conclusion = "insufficient evidence to identify root cause"
            elif primary:
                conclusion = (
                    f"primary={primary.category.value} status={primary.causal_status.value}"
                )
            else:
                conclusion = "no primary candidate"

        ev_key = "|".join(
            sorted(
                list(failure.evidence_refs)
                + list(failure.gap_refs)
                + [c.cause_id for c in causes]
            )
        )
        aid = make_assessment_id(failure.failure_id, ev_key)
        if aid in self._assessments:
            return self._assessments[aid]

        all_refs = list(
            dict.fromkeys(
                list(failure.evidence_refs)
                + list(extra_evidence_refs or [])
                + [r for c in causes for r in c.evidence_refs]
            )
        )
        prov = build_provenance(
            origin="rca_assessment",
            payload={
                "assessment_id": aid,
                "failure_id": failure.failure_id,
                "overall_status": overall_status.value,
                "primary": primary.category.value if primary else None,
            },
        )
        assessment = RootCauseAssessment(
            assessment_id=aid,
            failure_id=failure.failure_id,
            timestamp=utc_now(),
            primary_candidate=primary,
            contributing_causes=list(contrib),
            overall_status=overall_status,
            conclusion=conclusion,
            evidence_refs=all_refs,
            gap_refs=list(failure.gap_refs),
            strategy_ref=failure.strategy_ref,
            experiment_ref=failure.experiment_ref,
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            lifecycle_evidence_hint=lifecycle_evidence_hint,
        )
        self._assessments[aid] = assessment
        failure.status = FailureStatus.ASSESSED
        self._failures[failure.failure_id] = failure
        return assessment

    def get_failure(self, failure_id: str) -> Optional[FailureEvent]:
        return self._failures.get(failure_id)

    def get_assessment(self, assessment_id: str) -> Optional[RootCauseAssessment]:
        return self._assessments.get(assessment_id)

    def list_failures(self) -> list[FailureEvent]:
        return list(self._failures.values())

    def list_assessments(self) -> list[RootCauseAssessment]:
        return list(self._assessments.values())

    def assessments_for_strategy(self, strategy_ref: str) -> list[RootCauseAssessment]:
        return [a for a in self._assessments.values() if a.strategy_ref == strategy_ref]

    def assessments_for_experiment(
        self, experiment_ref: str
    ) -> list[RootCauseAssessment]:
        return [
            a for a in self._assessments.values() if a.experiment_ref == experiment_ref
        ]
