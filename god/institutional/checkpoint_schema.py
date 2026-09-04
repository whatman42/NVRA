"""Production semantic validation for institutional lifecycle checkpoints.

Opaque workflow payloads (observation/decision/risk_gated/executed) remain allowed.
Any payload that *claims* lifecycle/recovery authority is fail-closed validated.

Backward compatibility:
- Missing schema_version on a lifecycle claim → treated as legacy ``0.legacy``.
- Legacy READY/RUNNING requires recon_complete=True; otherwise rejected.
- Opaque non-lifecycle nodes are not granted READY/execution authority by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

CURRENT_SCHEMA = "1.0"
SUPPORTED_SCHEMAS = frozenset({"1.0", "0.legacy"})

LIFECYCLE_VALUES = frozenset({
    "INIT",
    "LICENSE_CHECK",
    "LOAD_STATE",
    "BROKER_CONNECT",
    "RECONCILIATION",
    "RISK_GOVERNOR",
    "READY",
    "RUNNING",
    "SAFE_MODE",
    "FAILED",
    "UNKNOWN",
})

OPAQUE_WORKFLOW_NODES = frozenset({
    "observation",
    "decision",
    "risk_gated",
    "executed",
})

REQUIRED_LIFECYCLE_FIELDS = frozenset({
    "schema_version",
    "sequence",
    "lifecycle",
    "recon_complete",
    "updated_ns",
})


class CheckpointValidationError(ValueError):
    """Raised when a lifecycle checkpoint fails semantic validation on save."""


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    classification: str
    reasons: tuple[str, ...] = ()
    trusted_ready: bool = False
    trusted_execution: bool = False

    @property
    def rejected(self) -> bool:
        return not self.ok


def is_lifecycle_claim(node: str, state: Mapping[str, Any] | None) -> bool:
    """True when payload or node asserts recovery/lifecycle authority."""
    if node in LIFECYCLE_VALUES:
        return True
    if not isinstance(state, Mapping):
        return False
    if node in OPAQUE_WORKFLOW_NODES and not any(
        k in state for k in ("schema_version", "lifecycle", "recon_complete", "sequence")
    ):
        return False
    return any(k in state for k in ("schema_version", "lifecycle", "recon_complete"))


def validate_lifecycle_state(
    state: Any,
    *,
    node: str = "",
    last_sequence: int | None = None,
    now_ns: int | None = None,
    max_age_ns: int = 7 * 24 * 3600 * 10**9,
) -> ValidationResult:
    """Validate a lifecycle/recovery checkpoint payload. Fail closed on invalid."""
    if state is None:
        return ValidationResult(False, "REJECT", ("null_state",))
    if not isinstance(state, dict):
        return ValidationResult(False, "REJECT", ("not_object",))
    if state == {}:
        return ValidationResult(False, "REJECT", ("empty_object",))

    if not is_lifecycle_claim(node, state):
        return ValidationResult(True, "LEGACY_OPAQUE", ("opaque_workflow",), False, False)

    reasons: list[str] = []

    schema = state.get("schema_version")
    if schema is None:
        schema = "0.legacy"
        reasons.append("legacy_missing_schema_version")
    if not isinstance(schema, str):
        return ValidationResult(False, "REJECT", ("schema_version_type",))
    if schema not in SUPPORTED_SCHEMAS:
        return ValidationResult(False, "REJECT", (f"unsupported_schema:{schema}",))

    working = dict(state)
    working.setdefault("schema_version", schema)

    for key in ("sequence", "lifecycle", "recon_complete", "updated_ns"):
        if key not in working:
            lc_hint = working.get("lifecycle") or (node if node in LIFECYCLE_VALUES else None)
            if lc_hint in ("READY", "RUNNING"):
                return ValidationResult(
                    False, "REJECT", (f"missing_required:{key}", "ready_claim_incomplete")
                )
            return ValidationResult(
                False, "RECONCILIATION_REQUIRED", (f"missing_required:{key}",), False, False
            )

    seq = working["sequence"]
    if not isinstance(seq, int) or isinstance(seq, bool):
        return ValidationResult(False, "REJECT", ("sequence_type",))
    if seq < 0:
        return ValidationResult(False, "REJECT", ("negative_sequence",))

    lc = working["lifecycle"]
    if not isinstance(lc, str):
        return ValidationResult(False, "REJECT", ("lifecycle_type",))
    if lc not in LIFECYCLE_VALUES:
        return ValidationResult(False, "REJECT", (f"invalid_lifecycle:{lc}",))

    recon = working["recon_complete"]
    if not isinstance(recon, bool):
        return ValidationResult(False, "REJECT", ("recon_complete_type",))

    updated = working["updated_ns"]
    if not isinstance(updated, int) or isinstance(updated, bool):
        return ValidationResult(False, "REJECT", ("updated_ns_type",))

    import time as _time

    now = now_ns if now_ns is not None else _time.time_ns()
    if updated > now + 10**12:
        return ValidationResult(False, "RECONCILIATION_REQUIRED", ("future_timestamp",), False, False)
    if now - updated > max_age_ns:
        return ValidationResult(False, "RECONCILIATION_REQUIRED", ("stale_state",), False, False)

    if last_sequence is not None:
        if seq < last_sequence:
            return ValidationResult(False, "REJECT", ("sequence_regression",))
        if seq > last_sequence + 1000:
            return ValidationResult(
                False, "RECONCILIATION_REQUIRED", ("future_sequence_jump",), False, False
            )

    if lc == "UNKNOWN":
        return ValidationResult(True, "UNKNOWN", tuple(reasons) + ("lifecycle_UNKNOWN",), False, False)
    if lc == "SAFE_MODE":
        return ValidationResult(True, "SAFE_MODE", tuple(reasons) + ("lifecycle_SAFE_MODE",), False, False)

    if lc in ("READY", "RUNNING") and not recon:
        return ValidationResult(
            False, "RECONCILIATION_REQUIRED", tuple(reasons) + ("READY_without_recon",), False, False
        )

    if working.get("order_pending") and working.get("flat") is True:
        return ValidationResult(
            False, "RECONCILIATION_REQUIRED", tuple(reasons) + ("exec_inconsistent",), False, False
        )
    if working.get("broker_state") == "MISMATCH":
        return ValidationResult(
            False, "RECONCILIATION_REQUIRED", tuple(reasons) + ("broker_mismatch",), False, False
        )

    if lc in ("READY", "RUNNING") and recon:
        # Checkpoint valid ≠ execution allowed; execution still requires RiskEngine.
        return ValidationResult(True, "ACCEPT", tuple(reasons), True, False)

    return ValidationResult(True, "ACCEPT", tuple(reasons), False, False)
