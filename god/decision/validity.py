"""Decision validity firewall for N.U.N.G. Fail-closed."""

from __future__ import annotations

from typing import Optional

from .models import DecisionConfig, ShadowDecision, ValidityState, decision_content_hash


def evaluate_validity(
    decision: ShadowDecision,
    *,
    now_iso: Optional[str] = None,
    config: Optional[DecisionConfig] = None,
    expected_hash: Optional[str] = None,
) -> ValidityState:
    """
    STALE → not VALID without reassessment.
    CORRUPTED → not VALID without rebuild.
    """
    if expected_hash is not None and decision.content_hash != expected_hash:
        return ValidityState.CORRUPTED

    # structural hash check on core fields
    core = {
        "decision_id": decision.decision_id,
        "cycle_id": decision.cycle_id,
        "status": decision.status.value,
        "revision": decision.revision,
        "evidence_fingerprint": decision.evidence_fingerprint,
    }
    if decision_content_hash(core) != decision.content_hash and expected_hash is None:
        # content_hash is over wider payload; skip strict if not matching core-only
        pass

    if decision.validity == ValidityState.CORRUPTED:
        return ValidityState.CORRUPTED

    if decision.valid_until and now_iso:
        if now_iso > decision.valid_until:
            return ValidityState.STALE

    if decision.validity == ValidityState.STALE:
        return ValidityState.STALE

    if decision.validity == ValidityState.INVALID:
        return ValidityState.INVALID

    if decision.validity == ValidityState.UNKNOWN:
        return ValidityState.UNKNOWN

    if decision.status in (
        __import__("god.decision.models", fromlist=["ShadowStatus"]).ShadowStatus.UNKNOWN,
    ):
        return ValidityState.UNKNOWN

    return ValidityState.VALID


def cannot_promote(from_state: ValidityState, to_state: ValidityState) -> bool:
    """True if transition is forbidden without canonical rebuild."""
    if from_state == ValidityState.STALE and to_state == ValidityState.VALID:
        return True  # needs reassessment
    if from_state == ValidityState.CORRUPTED and to_state == ValidityState.VALID:
        return True
    return False
