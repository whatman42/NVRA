"""Read-only strategy × candidate compatibility. Fail-closed."""

from __future__ import annotations

from typing import Any, Optional

from .models import Compatibility, SelectionStatus, UncertaintyLevel


def evaluate_compatibility(
    *,
    lifecycle: Optional[str],
    policy_permission: Optional[str] = None,
    has_validation_evidence: bool = False,
    drift_level: Optional[str] = None,
    regime_label: Optional[str] = None,
    strategy_regime_hint: Optional[str] = None,
    reality_gap_critical: bool = False,
) -> tuple[Compatibility, UncertaintyLevel, SelectionStatus, str]:
    """
    Returns (compatibility, uncertainty, selection_status, reason).
    Never invents COMPATIBLE when evidence is missing.
    """
    lc = (lifecycle or "").upper()
    if lc in ("RETIRED", "REJECTED"):
        return (
            Compatibility.INCOMPATIBLE,
            UncertaintyLevel.HIGH,
            SelectionStatus.BLOCKED,
            f"lifecycle={lc}",
        )

    perm = (policy_permission or "UNKNOWN").upper()
    if perm in ("BLOCK", "PAUSE"):
        return (
            Compatibility.INCOMPATIBLE,
            UncertaintyLevel.HIGH,
            SelectionStatus.BLOCKED,
            f"policy={perm}",
        )

    uncertainty = UncertaintyLevel.MEDIUM
    notes: list[str] = []

    if lc == "DEGRADED":
        uncertainty = UncertaintyLevel.HIGH
        notes.append("lifecycle=DEGRADED")

    if not has_validation_evidence:
        # soft: insufficient for firm SELECT
        notes.append("validation_evidence_absent")
        if uncertainty == UncertaintyLevel.MEDIUM:
            uncertainty = UncertaintyLevel.HIGH

    if reality_gap_critical:
        uncertainty = UncertaintyLevel.HIGH
        notes.append("reality_gap_critical")

    drift = (drift_level or "").upper()
    if drift in ("HIGH", "SEVERE"):
        uncertainty = UncertaintyLevel.HIGH
        notes.append(f"drift={drift}")

    # regime mismatch only if both sides present
    if (
        regime_label
        and strategy_regime_hint
        and regime_label.upper() != strategy_regime_hint.upper()
        and strategy_regime_hint.upper() not in ("", "UNKNOWN", "ANY")
    ):
        return (
            Compatibility.UNKNOWN,
            UncertaintyLevel.HIGH,
            SelectionStatus.UNKNOWN,
            "regime_mismatch",
        )

    if perm == "UNKNOWN":
        return (
            Compatibility.UNKNOWN,
            UncertaintyLevel.UNKNOWN,
            SelectionStatus.UNKNOWN,
            "policy=UNKNOWN",
        )

    if perm == "RESTRICT":
        return (
            Compatibility.COMPATIBLE,
            max_unc(uncertainty, UncertaintyLevel.MEDIUM),
            SelectionStatus.SELECTED,  # eligible for attention but restricted
            "policy=RESTRICT;" + ";".join(notes),
        )

    if perm == "ALLOW":
        # ALLOW is policy evidence only — still cognitive selection
        if uncertainty == UncertaintyLevel.HIGH and not has_validation_evidence:
            return (
                Compatibility.UNKNOWN,
                UncertaintyLevel.HIGH,
                SelectionStatus.INSUFFICIENT_EVIDENCE,
                "allow_but_insufficient_evidence",
            )
        unc = UncertaintyLevel.LOW if has_validation_evidence else uncertainty
        return (
            Compatibility.COMPATIBLE,
            unc,
            SelectionStatus.SELECTED,
            "policy=ALLOW;" + ";".join(notes),
        )

    # default fail-closed
    return (
        Compatibility.UNKNOWN,
        UncertaintyLevel.UNKNOWN,
        SelectionStatus.UNKNOWN,
        "default_unknown",
    )


def max_unc(a: UncertaintyLevel, b: UncertaintyLevel) -> UncertaintyLevel:
    order = {
        UncertaintyLevel.LOW: 0,
        UncertaintyLevel.MEDIUM: 1,
        UncertaintyLevel.HIGH: 2,
        UncertaintyLevel.UNKNOWN: 3,
    }
    return a if order[a] >= order[b] else b
