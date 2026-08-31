"""Deterministic model lifecycle state machine.

Legal transitions only. Illegal transitions rejected. Every transition auditable.
Never enables LIVE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# Canonical statuses
TRAINING = "training"
VALIDATED = "validated"
CANDIDATE = "candidate"
OOS = "oos"
CHALLENGER = "challenger"
PROMOTION_GATE = "promotion_gate"
CHAMPION = "champion"
REJECTED = "rejected"
ROLLED_BACK = "rolled_back"
RETIRED = "retired"

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    TRAINING: frozenset({VALIDATED, REJECTED}),
    VALIDATED: frozenset({CANDIDATE, REJECTED}),
    CANDIDATE: frozenset({OOS, REJECTED, CHALLENGER}),
    OOS: frozenset({CHALLENGER, REJECTED}),
    CHALLENGER: frozenset({PROMOTION_GATE, REJECTED}),
    PROMOTION_GATE: frozenset({CHAMPION, REJECTED, CHALLENGER}),
    CHAMPION: frozenset({ROLLED_BACK, RETIRED}),
    REJECTED: frozenset(),
    ROLLED_BACK: frozenset({RETIRED}),
    RETIRED: frozenset(),
}

# Registry uses a subset; map common registry statuses into the machine
REGISTRY_ALIASES = {
    "candidate": CANDIDATE,
    "champion": CHAMPION,
    "retired": RETIRED,
    "rolled_back": ROLLED_BACK,
    "challenger": CHALLENGER,
    "rejected": REJECTED,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TransitionResult:
    allowed: bool
    from_status: str
    to_status: str
    reason: str = ""
    model_id: str = ""
    model_version: str = ""
    recorded_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "recorded_at": self.recorded_at,
        }


def normalize_status(status: str) -> str:
    s = (status or "").strip().lower()
    return REGISTRY_ALIASES.get(s, s)


def is_legal_transition(from_status: str, to_status: str) -> bool:
    src = normalize_status(from_status)
    dst = normalize_status(to_status)
    if src == dst:
        return True
    allowed = LEGAL_TRANSITIONS.get(src)
    if allowed is None:
        # unknown source: only allow known terminal/registry targets via explicit map
        return dst in (CANDIDATE, CHAMPION, REJECTED, RETIRED, ROLLED_BACK)
    return dst in allowed


def validate_transition(
    from_status: str,
    to_status: str,
    *,
    model_id: str = "",
    model_version: str = "",
) -> TransitionResult:
    src = normalize_status(from_status)
    dst = normalize_status(to_status)
    ok = is_legal_transition(src, dst)
    return TransitionResult(
        allowed=ok,
        from_status=src,
        to_status=dst,
        reason="ok" if ok else f"illegal_transition:{src}->{dst}",
        model_id=model_id,
        model_version=model_version,
        recorded_at=_utc_now(),
    )


def apply_transition(
    current_status: str,
    target_status: str,
    *,
    model_id: str = "",
    model_version: str = "",
    audit: Any = None,
    force: bool = False,
) -> TransitionResult:
    """Validate and optionally audit a status change. Does not mutate registry."""
    result = validate_transition(
        current_status, target_status, model_id=model_id, model_version=model_version
    )
    if not result.allowed and not force:
        if audit is not None:
            try:
                audit.record(
                    "state_transition",
                    model_id=model_id,
                    model_version=model_version,
                    outcome="denied",
                    detail=result.to_dict(),
                )
            except Exception:
                pass
        return result

    if audit is not None:
        try:
            audit.record(
                "state_transition",
                model_id=model_id,
                model_version=model_version,
                outcome="success" if result.allowed else "forced",
                detail=result.to_dict(),
            )
        except Exception:
            pass
    return result
