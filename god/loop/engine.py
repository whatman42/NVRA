"""CognitiveLoopEngine — binds 4H→4I→4D/4E/4F into one autonomous cycle.

No daily manual pair/strategy selection.
No execution authority. ALLOW ≠ OPEN.
"""

from __future__ import annotations

from typing import Any, Optional

from god.discovery import DiscoveryEngine, Universe
from god.discovery.models import DiscoveryStatus
from god.memory.database import utc_now
from god.research.provenance import content_hash
from god.selection import SelectionEngine
from god.selection.models import SelectionResultStatus

from .checkpoint import CycleCheckpointStore
from .evidence_fusion import apply_evidence_to_status, fuse_evidence
from .models import (
    AttentionItem,
    AttentionStatus,
    CognitiveAttentionSet,
    CycleResult,
    CycleStatus,
    EvidenceContext,
    build_loop_provenance,
    make_cycle_id,
    make_set_id,
)
from .reassessment import reassess_set

LOOP_VERSION = "loop-4j-v1"


class CognitiveLoopEngine:
    """
    One-shot or repeated cognitive cycle:
      discover → select → fuse evidence → attention set → optional reassess
    """

    def __init__(
        self,
        universe: Universe,
        *,
        observations: Optional[dict[str, dict[str, Any]]] = None,
        strategy_registry: Any = None,
        policy_engine: Any = None,
        capital_engine: Any = None,
        drift_engine: Any = None,
        regime_engine: Any = None,
        reality_engine: Any = None,
        rca_engine: Any = None,
        max_matrix_cells: int = 256,
        max_attention: int = 50,
        memory_store: Any = None,
        now_iso: Optional[str] = None,
    ) -> None:
        self.universe = universe
        self.observations = observations or {}
        self.strategy_registry = strategy_registry
        self.policy_engine = policy_engine
        self.capital_engine = capital_engine
        self.drift_engine = drift_engine
        self.regime_engine = regime_engine
        self.reality_engine = reality_engine
        self.rca_engine = rca_engine
        self.max_matrix_cells = max_matrix_cells
        self.max_attention = max_attention
        self.now_iso = now_iso
        self._checkpoints = CycleCheckpointStore(memory_store)
        self._cache: dict[str, CycleResult] = {}

    def run_cycle(self) -> CycleResult:
        """
        Autonomous cycle. No pair= / strategy= parameters.
        """
        fp = content_hash(
            {
                "universe": self.universe.symbols(),
                "obs": {
                    k: list(v.get("values") or [])
                    for k, v in sorted(self.observations.items())
                },
                "v": LOOP_VERSION,
            }
        )
        cycle_id = make_cycle_id(fp, LOOP_VERSION)
        if cycle_id in self._cache:
            return self._cache[cycle_id]

        stages: list[str] = []

        # --- DISCOVER (4H) ---
        discovery = DiscoveryEngine(
            self.universe,
            strategy_registry=self.strategy_registry,
            policy_engine=self.policy_engine,
            observations=self.observations,
            now_iso=self.now_iso,
        )
        dr = discovery.discover()
        stages.append("DISCOVER")
        cp1 = self._checkpoints.save(
            cycle_id, "DISCOVER", {"discovery_result_id": dr.result_id}
        )

        if dr.status == DiscoveryStatus.NO_VALID_CANDIDATE or dr.universe_size == 0:
            result = self._finish(
                cycle_id,
                CycleStatus.NO_VALID_OPPORTUNITY,
                stages=stages,
                discovery_result_id=dr.result_id,
                checkpoint_id=cp1,
                notes="no_valid_candidate_upstream",
            )
            self._cache[cycle_id] = result
            return result

        # --- SELECT (4I) ---
        selection = SelectionEngine(
            strategy_registry=self.strategy_registry,
            policy_engine=self.policy_engine,
            capital_engine=self.capital_engine,
            max_matrix_cells=self.max_matrix_cells,
        )
        sr = selection.select(dr)
        stages.append("SELECT")
        cp2 = self._checkpoints.save(
            cycle_id,
            "SELECT",
            {
                "discovery_result_id": dr.result_id,
                "selection_id": sr.selection_id,
                "status": sr.status.value,
            },
        )

        # --- FUSE EVIDENCE (4D/4E/4F) per instrument in opportunities ---
        stages.append("FUSE")
        evidence_by_inst: dict[str, EvidenceContext] = {}
        # global fusion sample on first symbol with data
        default_ev = fuse_evidence(
            observations=self.observations,
            drift_engine=self.drift_engine,
            regime_engine=self.regime_engine,
            reality_engine=self.reality_engine,
            rca_engine=self.rca_engine,
            policy_engine=self.policy_engine,
            capital_engine=self.capital_engine,
            instrument=self.universe.symbols()[0] if self.universe.symbols() else None,
            now_iso=self.now_iso,
        )

        attention_items: list[AttentionItem] = []
        source_opps = list(sr.opportunities) or []
        # if selection empty, still allow restricted path inspection — but fail-closed
        for opp in source_opps[: self.max_attention]:
            inst = opp.instrument_ref
            if inst not in evidence_by_inst:
                evidence_by_inst[inst] = fuse_evidence(
                    observations=self.observations,
                    drift_engine=self.drift_engine,
                    regime_engine=self.regime_engine,
                    reality_engine=self.reality_engine,
                    policy_engine=self.policy_engine,
                    capital_engine=self.capital_engine,
                    instrument=inst,
                    now_iso=self.now_iso,
                )
            ev = evidence_by_inst[inst]
            base = (
                "SELECTED"
                if opp.selection_status.value == "SELECTED"
                else opp.selection_status.value
            )
            st_s, reason = apply_evidence_to_status(base_status=base, evidence=ev)
            try:
                st = AttentionStatus(st_s)
            except ValueError:
                st = AttentionStatus.UNKNOWN
            attention_items.append(
                AttentionItem(
                    opportunity_id=opp.opportunity_id,
                    instrument_ref=inst,
                    strategy_ref=opp.strategy_ref,
                    attention_priority=opp.attention_rank,
                    uncertainty=ev.uncertainty,
                    status=st,
                    evidence_refs=list(ev.evidence_refs),
                    drift_ref=ev.drift_ref,
                    regime_ref=ev.regime_ref,
                    reality_gap_ref=ev.reality_gap_ref,
                    policy_ref=ev.policy_ref,
                    candidate_id=opp.candidate_id,
                    notes=reason,
                )
            )

        # filter to cognitive attention (SELECTED/STILL_VALID) — not trades
        selected_items = [
            i
            for i in attention_items
            if i.status in (AttentionStatus.SELECTED, AttentionStatus.STILL_VALID)
        ]

        stages.append("ATTENTION")
        set_id = make_set_id(cycle_id, [i.opportunity_id for i in attention_items])
        if selected_items:
            status = CycleStatus.COMPLETE
            attn_status = CycleStatus.ATTENTION
        elif attention_items and all(
            i.status in (AttentionStatus.BLOCKED, AttentionStatus.NO_LONGER_VALID)
            for i in attention_items
        ):
            status = CycleStatus.BLOCKED
            attn_status = CycleStatus.BLOCKED
        elif not attention_items:
            if sr.status in (
                SelectionResultStatus.NO_VALID_OPPORTUNITY,
                SelectionResultStatus.INSUFFICIENT_EVIDENCE,
            ):
                status = CycleStatus.NO_VALID_OPPORTUNITY
            else:
                status = CycleStatus.NO_VALID_OPPORTUNITY
            attn_status = status
        else:
            # only UNKNOWN/DEGRADED etc.
            status = CycleStatus.INSUFFICIENT_EVIDENCE
            attn_status = CycleStatus.INSUFFICIENT_EVIDENCE

        attention = CognitiveAttentionSet(
            set_id=set_id,
            items=selected_items if selected_items else [],
            status=attn_status,
            discovery_result_id=dr.result_id,
            selection_id=sr.selection_id,
            evidence=default_ev,
            provenance=build_loop_provenance(
                {"set_id": set_id, "n": len(selected_items)}
            ),
            timestamp=utc_now(),
            notes="cognitive_attention_only",
        )

        cp3 = self._checkpoints.save(
            cycle_id,
            "ATTENTION",
            {
                "set_id": set_id,
                "selected_count": len(selected_items),
                "status": status.value,
            },
        )

        result = CycleResult(
            cycle_id=cycle_id,
            status=status,
            attention=attention,
            discovery_result_id=dr.result_id,
            selection_id=sr.selection_id,
            checkpoint_id=cp3,
            truncated=bool(sr.truncated),
            stages_completed=stages,
            provenance=build_loop_provenance(
                {"cycle_id": cycle_id, "status": status.value}
            ),
            timestamp=utc_now(),
            notes="autonomous_cognitive_cycle",
            metadata={
                "attention_candidates": len(attention_items),
                "attention_selected": len(selected_items),
                "default_drift": default_ev.drift_level,
                "default_regime": default_ev.regime_label,
                "default_policy": default_ev.policy_permission,
            },
        )
        self._cache[cycle_id] = result
        return result

    def reassess(self, previous: CycleResult) -> CycleResult:
        """Reassess prior attention with fresh evidence fusion."""
        if previous.attention is None or not previous.attention.items:
            return previous
        evidence_by_inst: dict[str, EvidenceContext] = {}
        for it in previous.attention.items:
            if it.instrument_ref not in evidence_by_inst:
                evidence_by_inst[it.instrument_ref] = fuse_evidence(
                    observations=self.observations,
                    drift_engine=self.drift_engine,
                    regime_engine=self.regime_engine,
                    reality_engine=self.reality_engine,
                    policy_engine=self.policy_engine,
                    capital_engine=self.capital_engine,
                    instrument=it.instrument_ref,
                    now_iso=self.now_iso,
                )
        new_items = reassess_set(previous.attention.items, evidence_by_inst)
        still = [
            i
            for i in new_items
            if i.status
            in (
                AttentionStatus.SELECTED,
                AttentionStatus.STILL_VALID,
                AttentionStatus.DEGRADED,
            )
        ]
        status = (
            CycleStatus.COMPLETE
            if any(
                i.status in (AttentionStatus.SELECTED, AttentionStatus.STILL_VALID)
                for i in still
            )
            else CycleStatus.NO_VALID_OPPORTUNITY
        )
        attn = CognitiveAttentionSet(
            set_id=previous.attention.set_id,
            items=still,
            status=status,
            discovery_result_id=previous.discovery_result_id,
            selection_id=previous.selection_id,
            evidence=previous.attention.evidence,
            provenance=build_loop_provenance(
                {"reassess": True, "set_id": previous.attention.set_id}
            ),
            timestamp=utc_now(),
            notes="reassessment",
        )
        stages = list(previous.stages_completed) + ["REASSESS"]
        cp = self._checkpoints.save(
            previous.cycle_id,
            "REASSESS",
            {"set_id": attn.set_id, "n": len(still)},
        )
        return CycleResult(
            cycle_id=previous.cycle_id + "-re",
            status=status,
            attention=attn,
            discovery_result_id=previous.discovery_result_id,
            selection_id=previous.selection_id,
            checkpoint_id=cp,
            stages_completed=stages,
            provenance=build_loop_provenance({"parent": previous.cycle_id}),
            timestamp=utc_now(),
            notes="reassessed",
        )

    def resume(self, cycle_id: str) -> Optional[dict[str, Any]]:
        cp = self._checkpoints.latest(cycle_id)
        if cp is None:
            return None
        if cp.get("status") == "CORRUPTED":
            return cp
        return {
            "status": "RESUME",
            "cycle_id": cycle_id,
            "stage": cp.get("stage"),
            "checkpoint": cp,
        }

    def _finish(
        self,
        cycle_id: str,
        status: CycleStatus,
        *,
        stages: list[str],
        discovery_result_id: Optional[str],
        checkpoint_id: Optional[str],
        notes: str,
    ) -> CycleResult:
        return CycleResult(
            cycle_id=cycle_id,
            status=status,
            attention=CognitiveAttentionSet(
                set_id=make_set_id(cycle_id, []),
                items=[],
                status=status,
                discovery_result_id=discovery_result_id,
                timestamp=utc_now(),
            ),
            discovery_result_id=discovery_result_id,
            checkpoint_id=checkpoint_id,
            stages_completed=stages,
            provenance=build_loop_provenance({"cycle_id": cycle_id, "status": status.value}),
            timestamp=utc_now(),
            notes=notes,
        )
