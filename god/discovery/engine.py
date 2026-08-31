"""DiscoveryEngine — autonomous universe discovery. No execution authority.

NO manual pair/strategy selection required for normal operation.
NO fallback to previous pair/strategy.
NO_VALID_CANDIDATE is a successful outcome when warranted.
"""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash

from .candidate import build_candidate
from .evidence import collect_strategy_refs, policy_permission
from .models import (
    Candidate,
    DiscoveryResult,
    DiscoveryStatus,
    EligibilityStatus,
    QualityStatus,
    make_result_id,
)
from .ranking import rank_candidates
from .scanner import Scanner
from .universe import Universe

DISCOVERY_VERSION = "discovery-4h-v1"


class DiscoveryEngine:
    def __init__(
        self,
        universe: Universe,
        *,
        strategy_registry: Any = None,
        policy_engine: Any = None,
        capital_engine: Any = None,
        observations: Optional[dict[str, dict[str, Any]]] = None,
        min_samples: int = 2,
        now_iso: Optional[str] = None,
        discovery_version: str = DISCOVERY_VERSION,
    ) -> None:
        self.universe = universe
        self.strategy_registry = strategy_registry
        self.policy_engine = policy_engine
        self.capital_engine = capital_engine
        self.observations = observations or {}
        self.min_samples = min_samples
        self.now_iso = now_iso
        self.discovery_version = discovery_version
        self._results: dict[str, DiscoveryResult] = {}

    def discover(self) -> DiscoveryResult:
        """
        Autonomous discovery over configured universe.
        Does not require user-selected pair or strategy.
        Never falls back to previous pair/strategy.
        """
        universe_key = content_hash(self.universe.symbols())
        scanner = Scanner(
            self.universe,
            observations=self.observations,
            min_samples=self.min_samples,
            now_iso=self.now_iso,
        )
        scanned = scanner.scan_all()
        analyzed = len(scanned)

        if self.universe.is_empty() or analyzed == 0:
            return self._finalize(
                universe_key,
                [],
                analyzed=0,
                insufficient=[],
                notes="empty_universe_or_no_scan",
            )

        strategies = collect_strategy_refs(self.strategy_registry)
        # Filter non-terminal strategies for candidate pairing (read-only)
        usable_strategies = [
            s
            for s in strategies
            if s.get("lifecycle") not in ("RETIRED", "REJECTED")
        ]

        enriched: list[Candidate] = []
        insufficient: list[str] = []

        for base in scanned:
            if base.quality_status in (
                QualityStatus.INVALID,
                QualityStatus.INSUFFICIENT_DATA,
                QualityStatus.STALE,
            ):
                insufficient.append(base.instrument_ref)
                enriched.append(base)
                continue

            if not usable_strategies:
                # quality ok but no strategy candidate → still not executable discovery
                c = build_candidate(
                    base.instrument_ref,
                    quality_status=base.quality_status,
                    eligibility=EligibilityStatus.INSUFFICIENT_DATA,
                    uncertainty="HIGH",
                    evidence_refs=list(base.evidence_refs),
                    notes="no_valid_strategy_candidate",
                )
                enriched.append(c)
                insufficient.append(base.instrument_ref)
                continue

            # Evaluate each strategy independently (no auto previous-strategy fallback)
            for sref in usable_strategies:
                sid = sref["strategy_id"]
                lifecycle = sref.get("lifecycle")
                perm, decision_id = policy_permission(
                    self.policy_engine,
                    strategy_lifecycle=lifecycle,
                    evidence_refs=[base.candidate_id],
                )
                eligibility = self._map_permission_to_eligibility(perm, lifecycle)
                policy_refs = [decision_id] if decision_id else []
                capital_refs: list[str] = []
                if self.capital_engine is not None:
                    try:
                        capital_refs = [str(self.capital_engine.state.value)]
                    except Exception:
                        capital_refs = []

                c = build_candidate(
                    base.instrument_ref,
                    strategy_ref=sid,
                    quality_status=base.quality_status,
                    eligibility=eligibility,
                    uncertainty="MODERATE" if eligibility == EligibilityStatus.ELIGIBLE else "HIGH",
                    evidence_refs=list(base.evidence_refs),
                    policy_refs=policy_refs,
                    capital_refs=capital_refs,
                    ranking_metadata={"policy_permission": perm},
                    notes=f"policy={perm};lifecycle={lifecycle}",
                )
                enriched.append(c)

        return self._finalize(
            universe_key,
            enriched,
            analyzed=analyzed,
            insufficient=insufficient,
            notes="autonomous_scan_complete",
        )

    def _map_permission_to_eligibility(
        self, permission: str, lifecycle: Optional[str]
    ) -> EligibilityStatus:
        # NEVER maps to OPEN/BUY/SELL — eligibility for discovery only
        if lifecycle in ("RETIRED", "REJECTED"):
            return EligibilityStatus.BLOCKED
        p = (permission or "UNKNOWN").upper()
        if p == "BLOCK":
            return EligibilityStatus.BLOCKED
        if p == "PAUSE":
            return EligibilityStatus.BLOCKED
        if p == "RESTRICT":
            return EligibilityStatus.RESTRICTED
        if p == "ALLOW":
            return EligibilityStatus.ELIGIBLE
        if p == "UNKNOWN":
            return EligibilityStatus.UNKNOWN
        return EligibilityStatus.UNKNOWN

    def _finalize(
        self,
        universe_key: str,
        candidates: list[Candidate],
        *,
        analyzed: int,
        insufficient: list[str],
        notes: str,
    ) -> DiscoveryResult:
        ranked = rank_candidates(candidates)
        eligible = [c for c in ranked if c.eligibility == EligibilityStatus.ELIGIBLE]
        restricted = [c for c in ranked if c.eligibility == EligibilityStatus.RESTRICTED]
        blocked = [
            c
            for c in ranked
            if c.eligibility
            in (EligibilityStatus.BLOCKED, EligibilityStatus.INELIGIBLE)
        ]

        if eligible:
            status = DiscoveryStatus.ELIGIBLE
        elif restricted:
            status = DiscoveryStatus.RESTRICTED
        elif not candidates or (
            not eligible and not restricted and analyzed >= 0
        ):
            # no eligible/restricted → abstention
            if insufficient and not blocked and not eligible and not restricted:
                status = DiscoveryStatus.INSUFFICIENT_DATA
            elif not eligible and not restricted:
                status = DiscoveryStatus.NO_VALID_CANDIDATE
            else:
                status = DiscoveryStatus.BLOCKED
        else:
            status = DiscoveryStatus.NO_VALID_CANDIDATE

        # empty universe special case
        if self.universe.is_empty():
            status = DiscoveryStatus.NO_VALID_CANDIDATE

        fingerprint = content_hash(
            {
                "status": status.value,
                "ids": [c.candidate_id for c in ranked],
                "elig": [c.eligibility.value for c in ranked],
            }
        )
        rid = make_result_id(universe_key, self.discovery_version, fingerprint)
        if rid in self._results:
            return self._results[rid]

        prov = build_provenance(
            origin="discovery_result",
            payload={
                "result_id": rid,
                "status": status.value,
                "universe_size": self.universe.size(),
            },
        )
        result = DiscoveryResult(
            result_id=rid,
            status=status,
            universe_size=self.universe.size(),
            analyzed_count=analyzed,
            eligible_candidates=eligible,
            restricted_candidates=restricted,
            blocked_candidates=blocked,
            insufficient_data=list(dict.fromkeys(insufficient)),
            ranking=[c.candidate_id for c in ranked],
            evidence_refs=[c.candidate_id for c in ranked],
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            discovery_version=self.discovery_version,
            timestamp=utc_now(),
            notes=notes,
        )
        self._results[rid] = result
        return result
