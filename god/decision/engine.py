"""Shadow Decision Engine for N.U.N.G. — closed-loop reassessment. PRE-EXECUTION."""

from __future__ import annotations

from typing import Any, Optional

from god.loop import CognitiveLoopEngine, CycleResult, CycleStatus
from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import (
    DecisionConfig,
    ShadowDecision,
    ShadowStatus,
    ValidityState,
    build_decision_provenance,
    decision_content_hash,
    evidence_fingerprint,
    make_decision_id,
)
from .reassessment import ReassessmentService
from .shadow import ShadowDecisionStore
from .validity import evaluate_validity


class ShadowDecisionEngine:
    """
    Create / revise shadow decisions from cycle results.
    Invoke loop.reassess via ReassessmentService.
    """

    def __init__(
        self,
        *,
        config: Optional[DecisionConfig] = None,
        loop_engine: Optional[CognitiveLoopEngine] = None,
        ledger: Any = None,
    ) -> None:
        self.config = config or DecisionConfig()
        self.loop_engine = loop_engine
        self.ledger = ledger  # optional CognitiveDecisionLedger
        self.store = ShadowDecisionStore(self.config)
        self.reassessment = ReassessmentService(self.config)
        self._last_cycle: Optional[CycleResult] = None

    def ingest_cycle(
        self,
        cycle: CycleResult,
        *,
        correlation_id: Optional[str] = None,
        now_iso: Optional[str] = None,
    ) -> list[ShadowDecision]:
        """Materialize shadow decisions from a cognitive cycle result."""
        self._last_cycle = cycle
        corr = correlation_id or ("corr-" + (cycle.cycle_id or "x")[:20])
        now = now_iso or utc_now()
        out: list[ShadowDecision] = []

        items = []
        if cycle.attention and cycle.attention.items:
            items = cycle.attention.items
        elif cycle.status in (
            CycleStatus.NO_VALID_OPPORTUNITY,
            CycleStatus.INSUFFICIENT_EVIDENCE,
            CycleStatus.BLOCKED,
        ):
            # single abstention decision
            dec = self._make_decision(
                cycle_id=cycle.cycle_id,
                correlation_id=corr,
                status=self._map_cycle_status(cycle.status),
                opportunity_id=None,
                symbol=None,
                strategy_ref=None,
                evidence_refs=[],
                revision=1,
                parent=None,
                reason_codes=[cycle.status.value],
                now=now,
                notes=cycle.notes,
            )
            out.append(self.store.put(dec))
            return out

        for it in items:
            refs = list(it.evidence_refs or [])[: self.config.max_evidence_refs]
            st = self._map_attention_status(it.status.value if hasattr(it.status, "value") else str(it.status))
            dec = self._make_decision(
                cycle_id=cycle.cycle_id,
                correlation_id=corr,
                status=st,
                opportunity_id=it.opportunity_id,
                symbol=it.instrument_ref,
                strategy_ref=it.strategy_ref,
                evidence_refs=refs,
                revision=1,
                parent=None,
                reason_codes=[],
                now=now,
                notes=it.notes or "",
                policy_status=None,
                extra_meta={"attention_priority": it.attention_priority},
            )
            out.append(self.store.put(dec))
        return out

    def force_reassess(
        self,
        *,
        previous: Optional[CycleResult] = None,
        reason: str = "FORCE_REASSESS",
        correlation_id: Optional[str] = None,
        now_iso: Optional[str] = None,
    ) -> tuple[Optional[CycleResult], list[ShadowDecision], bool]:
        """
        Invoke CognitiveLoopEngine.reassess and revise shadow decisions.
        Returns (cycle_result, decisions, is_new_trigger).
        """
        prev = previous or self._last_cycle
        if prev is None or self.loop_engine is None:
            return None, [], False
        result, is_new = self.reassessment.reassess(
            self.loop_engine, prev, reason=reason, evidence_fp=prev.cycle_id
        )
        if not is_new:
            # RETURN_EXISTING — return latest stored for this cycle family
            return prev, self.store.recent(10), False

        decisions = self._revise_from_reassess(
            prev, result, correlation_id=correlation_id, now_iso=now_iso
        )
        self._last_cycle = result
        return result, decisions, True

    def evidence_trigger(
        self,
        *,
        evidence_fp: str,
        reason: str = "EVIDENCE_UPDATE",
        previous: Optional[CycleResult] = None,
        correlation_id: Optional[str] = None,
        now_iso: Optional[str] = None,
    ) -> tuple[Optional[CycleResult], list[ShadowDecision], bool]:
        prev = previous or self._last_cycle
        if prev is None or self.loop_engine is None:
            return None, [], False
        result, is_new = self.reassessment.reassess(
            self.loop_engine,
            prev,
            reason=reason,
            evidence_fp=evidence_fp,
        )
        if not is_new:
            return prev, self.store.recent(10), False
        decisions = self._revise_from_reassess(
            prev, result, correlation_id=correlation_id, now_iso=now_iso
        )
        self._last_cycle = result
        return result, decisions, True

    def check_validity(
        self, decision_id: str, *, now_iso: Optional[str] = None
    ) -> ValidityState:
        d = self.store.get(decision_id)
        if d is None:
            return ValidityState.UNKNOWN
        return evaluate_validity(d, now_iso=now_iso, config=self.config)

    def _revise_from_reassess(
        self,
        previous: CycleResult,
        result: CycleResult,
        *,
        correlation_id: Optional[str],
        now_iso: Optional[str],
    ) -> list[ShadowDecision]:
        corr = correlation_id or ("corr-" + result.cycle_id[:20])
        now = now_iso or utc_now()
        out: list[ShadowDecision] = []
        # find previous shadow decisions for same opportunities
        prev_decisions = [
            d
            for d in self.store.recent(self.config.max_decisions)
            if d.cycle_id == previous.cycle_id or d.cycle_id.startswith(previous.cycle_id)
        ]
        by_opp = {d.opportunity_id: d for d in prev_decisions if d.opportunity_id}

        items = result.attention.items if result.attention else []
        for it in items:
            parent = by_opp.get(it.opportunity_id)
            rev = (parent.revision + 1) if parent else 1
            st = self._map_attention_status(
                it.status.value if hasattr(it.status, "value") else str(it.status)
            )
            # policy: UNKNOWN/BLOCKED never become SELECTED via silent path
            if parent and parent.status == ShadowStatus.UNKNOWN and st == ShadowStatus.SELECTED:
                st = ShadowStatus.UNKNOWN
            if parent and parent.validity == ValidityState.CORRUPTED:
                # cannot promote corrupted to valid status path — mark invalid revision path
                st = ShadowStatus.NO_LONGER_VALID
            refs = list(it.evidence_refs or [])[: self.config.max_evidence_refs]
            dec = self._make_decision(
                cycle_id=result.cycle_id,
                correlation_id=corr,
                status=st,
                opportunity_id=it.opportunity_id,
                symbol=it.instrument_ref,
                strategy_ref=it.strategy_ref,
                evidence_refs=refs,
                revision=rev,
                parent=parent,
                reason_codes=["REASSESS"],
                now=now,
                notes=it.notes or "reassessed",
            )
            out.append(self.store.put(dec))

        if not items and result.status in (
            CycleStatus.NO_VALID_OPPORTUNITY,
            CycleStatus.INSUFFICIENT_EVIDENCE,
            CycleStatus.BLOCKED,
        ):
            parent = prev_decisions[-1] if prev_decisions else None
            rev = (parent.revision + 1) if parent else 1
            dec = self._make_decision(
                cycle_id=result.cycle_id,
                correlation_id=corr,
                status=self._map_cycle_status(result.status),
                opportunity_id=parent.opportunity_id if parent else None,
                symbol=parent.symbol if parent else None,
                strategy_ref=parent.strategy_ref if parent else None,
                evidence_refs=[],
                revision=rev,
                parent=parent,
                reason_codes=[result.status.value, "REASSESS"],
                now=now,
                notes=result.notes,
            )
            out.append(self.store.put(dec))
        return out

    def _make_decision(
        self,
        *,
        cycle_id: str,
        correlation_id: str,
        status: ShadowStatus,
        opportunity_id: Optional[str],
        symbol: Optional[str],
        strategy_ref: Optional[str],
        evidence_refs: list[str],
        revision: int,
        parent: Optional[ShadowDecision],
        reason_codes: list[str],
        now: str,
        notes: str,
        policy_status: Optional[str] = None,
        extra_meta: Optional[dict[str, Any]] = None,
    ) -> ShadowDecision:
        efp = evidence_fingerprint(evidence_refs)
        did = make_decision_id(
            cycle_id, opportunity_id, efp, status.value, revision
        )
        core = {
            "decision_id": did,
            "cycle_id": cycle_id,
            "status": status.value,
            "revision": revision,
            "evidence_fingerprint": efp,
        }
        ch = decision_content_hash(core)
        validity = ValidityState.VALID
        if status in (ShadowStatus.UNKNOWN, ShadowStatus.INSUFFICIENT_EVIDENCE):
            validity = ValidityState.UNKNOWN
        if status == ShadowStatus.BLOCKED:
            validity = ValidityState.INVALID
        if status == ShadowStatus.NO_LONGER_VALID:
            validity = ValidityState.INVALID

        valid_until = None
        if self.config.decision_ttl_seconds is not None:
            # store as note; actual STALE check compares now_iso > valid_until if set
            # without datetime math on all formats, leave None unless caller sets
            pass

        return ShadowDecision(
            decision_id=did,
            cycle_id=cycle_id,
            correlation_id=correlation_id,
            status=status,
            validity=validity,
            revision=revision,
            content_hash=ch,
            created_at=now,
            opportunity_id=opportunity_id,
            symbol=symbol,
            strategy_ref=strategy_ref,
            policy_status=policy_status,
            evidence_refs=list(evidence_refs),
            evidence_fingerprint=efp,
            parent_decision_id=parent.decision_id if parent else None,
            parent_revision=parent.revision if parent else None,
            valid_until=valid_until,
            provenance=build_decision_provenance(core),
            reason_codes=list(reason_codes),
            notes=notes,
            metadata=dict(extra_meta or {}),
        )

    def _map_attention_status(self, s: str) -> ShadowStatus:
        try:
            return ShadowStatus(s)
        except ValueError:
            mapping = {
                "SELECTED": ShadowStatus.SELECTED,
                "STILL_VALID": ShadowStatus.STILL_VALID,
                "DEGRADED": ShadowStatus.DEGRADED,
                "BLOCKED": ShadowStatus.BLOCKED,
                "UNKNOWN": ShadowStatus.UNKNOWN,
                "NO_LONGER_VALID": ShadowStatus.NO_LONGER_VALID,
                "INSUFFICIENT_EVIDENCE": ShadowStatus.INSUFFICIENT_EVIDENCE,
            }
            return mapping.get(s.upper(), ShadowStatus.UNKNOWN)

    def _map_cycle_status(self, st: CycleStatus) -> ShadowStatus:
        return {
            CycleStatus.NO_VALID_OPPORTUNITY: ShadowStatus.NO_VALID_OPPORTUNITY,
            CycleStatus.INSUFFICIENT_EVIDENCE: ShadowStatus.INSUFFICIENT_EVIDENCE,
            CycleStatus.BLOCKED: ShadowStatus.BLOCKED,
            CycleStatus.COMPLETE: ShadowStatus.SELECTED,
            CycleStatus.ATTENTION: ShadowStatus.SELECTED,
            CycleStatus.UNKNOWN: ShadowStatus.UNKNOWN,
            CycleStatus.CORRUPTED: ShadowStatus.NO_LONGER_VALID,
        }.get(st, ShadowStatus.UNKNOWN)
