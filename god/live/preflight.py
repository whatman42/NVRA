"""LIVE preflight — UNKNOWN != PASS."""

from __future__ import annotations

from typing import Optional

from .models import MANDATORY_PREFLIGHT, PreflightReport, PreflightStatus


def run_preflight(
    *,
    checks: Optional[dict[str, PreflightStatus]] = None,
    force_all_unknown: bool = False,
) -> PreflightReport:
    """
    Evaluate mandatory preflight.
    Default: all UNKNOWN → overall FAIL (cannot arm).
    Caller supplies authoritative check results.
    """
    results: dict[str, PreflightStatus] = {}
    reasons: list[str] = []
    supplied = checks or {}

    for name in MANDATORY_PREFLIGHT:
        if force_all_unknown:
            st = PreflightStatus.UNKNOWN
        else:
            st = supplied.get(name, PreflightStatus.UNKNOWN)
        results[name] = st
        if st != PreflightStatus.PASS:
            reasons.append(f"{name}={st.value}")

    if any(v == PreflightStatus.FAIL for v in results.values()):
        overall = PreflightStatus.FAIL
    elif any(v == PreflightStatus.UNKNOWN for v in results.values()):
        overall = PreflightStatus.FAIL  # UNKNOWN != SAFE
        if "unknown_checks" not in reasons:
            reasons.append("unknown_checks_block_arm")
    else:
        overall = PreflightStatus.PASS

    return PreflightReport(overall=overall, checks=results, reasons=reasons)
