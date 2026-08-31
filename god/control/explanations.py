"""Structured cognitive explanations for N.U.N.G. — evidence only, no invented rationale."""

from __future__ import annotations

from typing import Optional, Sequence

from god.research.provenance import content_hash

from .models import (
    CognitiveExplanation,
    ControlConfig,
    DecisionStatus,
    build_control_provenance,
)


def explain_decision(
    status: DecisionStatus,
    *,
    reason_codes: Optional[Sequence[str]] = None,
    evidence_refs: Optional[Sequence[str]] = None,
    summary: Optional[str] = None,
    config: Optional[ControlConfig] = None,
) -> CognitiveExplanation:
    cfg = config or ControlConfig()
    codes = tuple(list(reason_codes or [])[: cfg.max_reason_codes])
    refs = tuple(list(evidence_refs or [])[: cfg.max_evidence_refs])
    if summary is None:
        summary = _default_summary(status, codes)
    payload = {
        "status": status.value,
        "reason_codes": list(codes),
        "evidence_refs": list(refs),
        "summary": summary,
    }
    ch = content_hash(payload)
    return CognitiveExplanation(
        status=status,
        reason_codes=codes,
        evidence_refs=refs,
        summary=summary,
        content_hash=ch,
        provenance=build_control_provenance(payload),
    )


def _default_summary(status: DecisionStatus, codes: tuple[str, ...]) -> str:
    base = {
        DecisionStatus.SELECTED: "Attention candidate selected under current evidence",
        DecisionStatus.DEGRADED: "Attention degraded due to adverse evidence",
        DecisionStatus.BLOCKED: "Attention blocked by policy or safety state",
        DecisionStatus.UNKNOWN: "Insufficient certainty; fail-closed to UNKNOWN",
        DecisionStatus.INSUFFICIENT_EVIDENCE: "Evidence insufficient for attention",
        DecisionStatus.NO_VALID_OPPORTUNITY: "No valid opportunity in this cycle",
        DecisionStatus.COMPLETED: "Cognitive cycle completed",
        DecisionStatus.FAILED: "Cognitive cycle failed",
    }.get(status, "Cognitive decision recorded")
    if codes:
        return f"{base}; reasons={','.join(codes)}"
    return base


def reasons_from_runtime_notes(notes: str) -> list[str]:
    """Map known note fragments to reason codes — no speculation."""
    n = (notes or "").upper()
    codes: list[str] = []
    if "DRIFT" in n and ("HIGH" in n or "SEVERE" in n):
        codes.append("DRIFT_HIGH")
    if "REALITY_GAP" in n or "GAP_CRITICAL" in n:
        codes.append("REALITY_GAP_CRITICAL")
    if "POLICY=BLOCK" in n or "BLOCK" in n:
        codes.append("POLICY_BLOCK")
    if "POLICY=UNKNOWN" in n:
        codes.append("POLICY_UNKNOWN")
    if "STALE" in n:
        codes.append("STALE_DATA")
    if "NO_VALID" in n:
        codes.append("NO_VALID")
    if "INSUFFICIENT" in n:
        codes.append("INSUFFICIENT_EVIDENCE")
    return codes
