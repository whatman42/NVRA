"""Bounded candidate × strategy matrix evaluation."""

from __future__ import annotations

from typing import Any, Optional

from god.discovery.models import Candidate, DiscoveryResult, EligibilityStatus

from .compatibility import evaluate_compatibility
from .models import (
    Compatibility,
    Opportunity,
    SelectionStatus,
    UncertaintyLevel,
    make_opportunity_id,
)
from .provenance import selection_provenance


def _usable_strategies(strategy_registry: Any) -> list[dict[str, str]]:
    if strategy_registry is None:
        return []
    out: list[dict[str, str]] = []
    try:
        for s in strategy_registry.list_all():
            lc = getattr(s.lifecycle_state, "value", str(s.lifecycle_state))
            out.append({"strategy_id": s.strategy_id, "lifecycle": lc})
    except Exception:
        return []
    return out


def _all_candidates(dr: DiscoveryResult) -> list[Candidate]:
    seen: set[str] = set()
    ordered: list[Candidate] = []
    for group in (
        dr.eligible_candidates,
        dr.restricted_candidates,
        dr.blocked_candidates,
    ):
        for c in group:
            if c.candidate_id not in seen:
                seen.add(c.candidate_id)
                ordered.append(c)
    # also walk ranking ids if needed — candidates already covered
    return ordered


class MatrixEvaluator:
    def __init__(self, *, max_matrix_cells: int = 256) -> None:
        self.max_matrix_cells = max_matrix_cells

    def evaluate(
        self,
        discovery_result: DiscoveryResult,
        strategy_registry: Any = None,
        *,
        policy_permission_by_strategy: Optional[dict[str, str]] = None,
    ) -> tuple[list[Opportunity], bool]:
        """
        Returns (opportunities, truncated).
        policy_permission_by_strategy: optional map strategy_id -> permission value.
        """
        strategies = _usable_strategies(strategy_registry)
        candidates = _all_candidates(discovery_result)
        perm_map = policy_permission_by_strategy or {}

        # If discovery already paired strategy_ref on candidates, prefer those pairs first
        pairs: list[tuple[Candidate, Optional[str], Optional[str]]] = []
        for c in candidates:
            if c.strategy_ref:
                lc = None
                for s in strategies:
                    if s["strategy_id"] == c.strategy_ref:
                        lc = s["lifecycle"]
                        break
                pairs.append((c, c.strategy_ref, lc))
            elif strategies:
                for s in strategies:
                    pairs.append((c, s["strategy_id"], s["lifecycle"]))
            else:
                pairs.append((c, None, None))

        truncated = False
        if len(pairs) > self.max_matrix_cells:
            pairs = pairs[: self.max_matrix_cells]
            truncated = True

        opportunities: list[Opportunity] = []
        for idx, (c, sid, lc) in enumerate(pairs):
            perm = None
            if sid and sid in perm_map:
                perm = perm_map[sid]
            elif c.ranking_metadata.get("policy_permission"):
                perm = str(c.ranking_metadata["policy_permission"])
            elif c.eligibility == EligibilityStatus.BLOCKED:
                perm = "BLOCK"
            elif c.eligibility == EligibilityStatus.RESTRICTED:
                perm = "RESTRICT"
            elif c.eligibility == EligibilityStatus.ELIGIBLE:
                perm = "ALLOW"
            elif c.eligibility == EligibilityStatus.INSUFFICIENT_DATA:
                perm = "UNKNOWN"

            has_val = bool(c.validation_refs) or bool(c.evidence_refs)
            # if strategy exists, treat discovery path as partial evidence
            if sid and c.quality_status.value == "VALID":
                has_val = has_val or True  # quality-valid candidate counts as minimal evidence

            if sid is None:
                comp = Compatibility.UNKNOWN
                unc = UncertaintyLevel.HIGH
                st = SelectionStatus.INSUFFICIENT_EVIDENCE
                reason = "no_strategy"
            else:
                comp, unc, st, reason = evaluate_compatibility(
                    lifecycle=lc,
                    policy_permission=perm,
                    has_validation_evidence=has_val,
                    drift_level=None,
                    reality_gap_critical=False,
                )

            oid = make_opportunity_id(
                c.candidate_id, sid, comp.value, unc.value
            )
            payload = {
                "opportunity_id": oid,
                "candidate_id": c.candidate_id,
                "strategy_ref": sid,
                "status": st.value,
            }
            opportunities.append(
                Opportunity(
                    opportunity_id=oid,
                    candidate_id=c.candidate_id,
                    instrument_ref=c.instrument_ref,
                    strategy_ref=sid,
                    compatibility=comp,
                    evidence_refs=tuple(c.evidence_refs or []),
                    uncertainty=unc,
                    attention_rank=idx,  # temporary; ranker reassigns
                    selection_status=st,
                    provenance=selection_provenance(payload),
                    content_hash=payload and __import__(
                        "god.research.provenance", fromlist=["content_hash"]
                    ).content_hash(payload),
                    notes=reason,
                    metadata={
                        "discovery_rank": idx,
                        "eligibility": c.eligibility.value,
                    },
                )
            )
        return opportunities, truncated
