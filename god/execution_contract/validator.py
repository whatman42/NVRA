"""Execution intent validator for N.U.N.G. — fail-closed."""

from __future__ import annotations

from typing import Optional

from god.research.provenance import content_hash

from .models import ExecutionIntent, IntentStatus


# Decision statuses that may produce VALID intents (paper path only)
_ELIGIBLE = frozenset(
    {
        "SELECTED",
        "STILL_VALID",
        "DEGRADED",  # may paper-only with notes; still validated as structure-ok
    }
)

_REJECT_STATUSES = frozenset(
    {
        "UNKNOWN",
        "BLOCKED",
        "INVALID",
        "STALE",
        "CORRUPTED",
        "NO_LONGER_VALID",
        "INSUFFICIENT_EVIDENCE",
        "NO_VALID_OPPORTUNITY",
    }
)


def validate_intent(
    intent: ExecutionIntent,
    *,
    now_iso: Optional[str] = None,
) -> tuple[IntentStatus, str]:
    """
    Returns (status, reason).
    Only VALID may proceed to NullExecutionProvider.
    """
    if not intent.decision_id or not str(intent.decision_id).strip():
        return IntentStatus.INVALID, "missing_decision_id"
    if not intent.cycle_id or not str(intent.cycle_id).strip():
        return IntentStatus.INVALID, "missing_cycle_id"
    if not intent.opportunity_id or not str(intent.opportunity_id).strip():
        return IntentStatus.INVALID, "missing_opportunity_id"
    if not intent.symbol or not str(intent.symbol).strip():
        return IntentStatus.INVALID, "missing_symbol"

    # hash integrity
    core = {
        "decision_id": intent.decision_id,
        "cycle_id": intent.cycle_id,
        "opportunity_id": intent.opportunity_id,
        "symbol": intent.symbol,
        "strategy_ref": intent.strategy_ref,
        "decision_status": intent.decision_status,
        "intent_action": intent.intent_action.value,
        "schema_version": intent.schema_version,
    }
    expected = content_hash(core)
    # intent content_hash is over core; mismatch → CORRUPTED
    if intent.content_hash and intent.content_hash != expected:
        return IntentStatus.CORRUPTED, "hash_mismatch"

    if not intent.provenance:
        return IntentStatus.INVALID, "missing_provenance"

    if not intent.created_at:
        return IntentStatus.INVALID, "missing_created_at"

    if now_iso is not None:
        if intent.created_at > now_iso:
            return IntentStatus.INVALID, "future_created_at"
        if intent.valid_until and intent.valid_until < now_iso:
            return IntentStatus.STALE, "past_valid_until"

    ds = (intent.decision_status or "").upper()
    if ds in _REJECT_STATUSES or ds == "UNKNOWN":
        if ds == "BLOCKED":
            return IntentStatus.BLOCKED, "decision_blocked"
        if ds == "STALE":
            return IntentStatus.STALE, "decision_stale"
        if ds == "CORRUPTED":
            return IntentStatus.CORRUPTED, "decision_corrupted"
        if ds in ("UNKNOWN", "INSUFFICIENT_EVIDENCE"):
            return IntentStatus.UNKNOWN, "decision_unknown"
        return IntentStatus.INVALID, f"decision_status={ds}"

    if ds not in _ELIGIBLE and ds not in ("",):
        # non-eligible
        if ds not in _ELIGIBLE:
            return IntentStatus.BLOCKED, f"not_eligible:{ds}"

    if intent.intent_status == IntentStatus.CORRUPTED:
        return IntentStatus.CORRUPTED, "intent_marked_corrupted"

    return IntentStatus.VALID, "ok"


class ExecutionValidator:
    def validate(
        self, intent: ExecutionIntent, *, now_iso: Optional[str] = None
    ) -> tuple[bool, IntentStatus, str]:
        status, reason = validate_intent(intent, now_iso=now_iso)
        return status == IntentStatus.VALID, status, reason
