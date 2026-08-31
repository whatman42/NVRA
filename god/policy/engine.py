"""PolicyEngine — evaluate evidence → PolicyDecision. No execution authority."""

from __future__ import annotations

from typing import Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance

from .composition import compose
from .models import (
    Permission,
    PolicyDecision,
    PolicyEvidenceBundle,
    make_decision_id,
)

DEFAULT_POLICY_VERSION = "policy-4f-v1"


class PolicyEngine:
    """Fail-closed policy evaluation. NEVER maps permission to OPEN/BUY/SELL."""

    def __init__(self, policy_version: str = DEFAULT_POLICY_VERSION) -> None:
        self.policy_version = policy_version
        self._decisions: dict[str, PolicyDecision] = {}

    def evaluate(self, bundle: PolicyEvidenceBundle) -> PolicyDecision:
        # Malformed / untrusted provenance → restrictive
        if bundle.provenance is not None and not isinstance(bundle.provenance, dict):
            permission = Permission.UNKNOWN
            reasons = ["malformed_provenance"]
            trace = ["PROVENANCE:UNKNOWN:malformed"]
        elif bundle.has_execution_intent():
            permission = Permission.BLOCK
            reasons = ["evidence_bundle_contains_execution_intent_markers"]
            trace = ["SAFETY:BLOCK:execution_intent_in_evidence"]
        else:
            permission, reasons, trace = compose(bundle)

        fp = bundle.fingerprint()
        did = make_decision_id(fp, self.policy_version)
        if did in self._decisions:
            return self._decisions[did]

        all_refs = list(
            dict.fromkeys(
                list(bundle.evidence_refs)
                + list(bundle.reality_gap_refs)
                + list(bundle.rca_refs)
                + list(bundle.drift_refs)
                + list(bundle.regime_refs)
            )
        )
        prov = build_provenance(
            origin="policy_decision",
            payload={
                "decision_id": did,
                "permission": permission.value,
                "policy_version": self.policy_version,
                "fingerprint": fp,
            },
        )
        decision = PolicyDecision(
            decision_id=did,
            permission=permission,
            reasons=list(reasons),
            evidence_refs=all_refs,
            uncertainty=bundle.uncertainty or "UNKNOWN",
            policy_version=self.policy_version,
            composition_trace=list(trace),
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            timestamp=utc_now(),
        )
        self._decisions[did] = decision
        return decision

    def get(self, decision_id: str) -> Optional[PolicyDecision]:
        return self._decisions.get(decision_id)

    def list_all(self) -> list[PolicyDecision]:
        return list(self._decisions.values())
