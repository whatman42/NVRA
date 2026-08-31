"""SelectionEngine — autonomous opportunity selection for cognitive attention.

Does NOT require daily manual pair or strategy selection.
Does NOT execute trades. ALLOW ≠ OPEN.
"""

from __future__ import annotations

from typing import Any, Optional

from god.discovery.models import DiscoveryResult, DiscoveryStatus
from god.memory.database import utc_now

from .evaluator import MatrixEvaluator
from .models import (
    Opportunity,
    OpportunitySelectionResult,
    SelectionResultStatus,
    SelectionStatus,
    make_selection_id,
)
from .provenance import selection_provenance
from .ranking import rank_opportunities

SELECTION_VERSION = "selection-4i-v1"


class SelectionEngine:
    def __init__(
        self,
        *,
        strategy_registry: Any = None,
        policy_engine: Any = None,
        capital_engine: Any = None,
        max_matrix_cells: int = 256,
        selection_version: str = SELECTION_VERSION,
        memory_store: Any = None,
    ) -> None:
        self.strategy_registry = strategy_registry
        self.policy_engine = policy_engine
        self.capital_engine = capital_engine
        self.max_matrix_cells = max_matrix_cells
        self.selection_version = selection_version
        self._memory = memory_store
        self._cache: dict[str, OpportunitySelectionResult] = {}
        self._evaluator = MatrixEvaluator(max_matrix_cells=max_matrix_cells)

    def select(
        self,
        discovery_result: DiscoveryResult,
        *,
        universe_ref: Optional[str] = None,
    ) -> OpportunitySelectionResult:
        """
        Autonomous selection from a DiscoveryResult.
        No pair=, symbol=, strategy= parameters.
        """
        # Early abstention paths
        if discovery_result.universe_size == 0 or discovery_result.status in (
            DiscoveryStatus.NO_VALID_CANDIDATE,
        ):
            return self._empty_result(
                discovery_result,
                SelectionResultStatus.NO_VALID_OPPORTUNITY,
                universe_ref=universe_ref,
                notes="upstream_no_valid_candidate_or_empty_universe",
            )

        if discovery_result.status == DiscoveryStatus.INSUFFICIENT_DATA and not (
            discovery_result.eligible_candidates
            or discovery_result.restricted_candidates
        ):
            return self._empty_result(
                discovery_result,
                SelectionResultStatus.INSUFFICIENT_EVIDENCE,
                universe_ref=universe_ref,
                notes="upstream_insufficient_data",
            )

        opportunities, truncated = self._evaluator.evaluate(
            discovery_result,
            self.strategy_registry,
        )
        ranked = rank_opportunities(opportunities)

        selected = [
            o
            for o in ranked
            if o.selection_status == SelectionStatus.SELECTED
            and o.compatibility.value == "COMPATIBLE"
        ]
        # also allow RESTRICT path marked SELECTED with COMPATIBLE
        rejected = [
            o
            for o in ranked
            if o.selection_status
            in (
                SelectionStatus.BLOCKED,
                SelectionStatus.REJECTED,
                SelectionStatus.INSUFFICIENT_EVIDENCE,
            )
            or o.compatibility.value == "INCOMPATIBLE"
        ]

        if selected:
            status = SelectionResultStatus.SELECTED
        elif any(o.selection_status == SelectionStatus.UNKNOWN for o in ranked):
            status = SelectionResultStatus.UNKNOWN
        elif any(
            o.selection_status == SelectionStatus.INSUFFICIENT_EVIDENCE for o in ranked
        ):
            status = SelectionResultStatus.INSUFFICIENT_EVIDENCE
        elif rejected and not selected:
            status = SelectionResultStatus.NO_VALID_OPPORTUNITY
        else:
            status = SelectionResultStatus.NO_VALID_OPPORTUNITY

        if truncated and status == SelectionResultStatus.SELECTED:
            # still SELECTED but marked complete/truncated
            pass

        final_status = (
            SelectionResultStatus.COMPLETE if truncated and not selected else status
        )
        if truncated and selected:
            final_status = SelectionResultStatus.SELECTED

        if not ranked and not selected:
            final_status = SelectionResultStatus.NO_VALID_OPPORTUNITY

        oid_list = [o.opportunity_id for o in ranked]
        sid = make_selection_id(
            discovery_result.result_id,
            oid_list,
            final_status.value,
            self.selection_version,
        )
        if sid in self._cache:
            return self._cache[sid]

        prov = selection_provenance(
            {
                "selection_id": sid,
                "discovery_result_id": discovery_result.result_id,
                "status": final_status.value,
                "truncated": truncated,
            }
        )
        result = OpportunitySelectionResult(
            selection_id=sid,
            status=final_status,
            opportunities=selected if selected else [],
            rejected=rejected,
            universe_ref=universe_ref,
            discovery_result_id=discovery_result.result_id,
            selection_version=self.selection_version,
            provenance=prov,
            timestamp=utc_now(),
            truncated=truncated,
            notes="autonomous_selection",
            metadata={
                "ranked_count": len(ranked),
                "selected_count": len(selected),
                "rejected_count": len(rejected),
            },
        )
        # store full ranked in metadata for audit without treating all as "selected"
        result.metadata["all_ranked_ids"] = [o.opportunity_id for o in ranked]
        self._cache[sid] = result
        if self._memory is not None:
            try:
                import json

                self._memory.set_state(
                    f"orch_selection_v1:{sid}", json.dumps(result.to_dict())
                )
            except Exception:
                pass
        return result

    def _empty_result(
        self,
        discovery_result: DiscoveryResult,
        status: SelectionResultStatus,
        *,
        universe_ref: Optional[str],
        notes: str,
    ) -> OpportunitySelectionResult:
        sid = make_selection_id(
            discovery_result.result_id,
            [],
            status.value,
            self.selection_version,
        )
        if sid in self._cache:
            return self._cache[sid]
        prov = selection_provenance(
            {
                "selection_id": sid,
                "discovery_result_id": discovery_result.result_id,
                "status": status.value,
            }
        )
        result = OpportunitySelectionResult(
            selection_id=sid,
            status=status,
            opportunities=[],
            rejected=[],
            universe_ref=universe_ref,
            discovery_result_id=discovery_result.result_id,
            selection_version=self.selection_version,
            provenance=prov,
            timestamp=utc_now(),
            truncated=False,
            notes=notes,
        )
        self._cache[sid] = result
        return result
