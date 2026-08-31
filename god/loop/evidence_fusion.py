"""Fuse 4D/4E/4F evidence for selection-aware attention. No fabricated evidence."""

from __future__ import annotations

from typing import Any, Optional

from god.research.provenance import content_hash

from .models import EvidenceContext, build_loop_provenance


def fuse_evidence(
    *,
    observations: Optional[dict[str, dict[str, Any]]] = None,
    drift_engine: Any = None,
    regime_engine: Any = None,
    reality_engine: Any = None,
    rca_engine: Any = None,
    policy_engine: Any = None,
    capital_engine: Any = None,
    instrument: Optional[str] = None,
    now_iso: Optional[str] = None,
) -> EvidenceContext:
    """
    Build EvidenceContext from real engines when available.
    Missing engines → UNKNOWN fields (fail-closed, no synthetic ALLOW).
    """
    ctx = EvidenceContext(uncertainty="UNKNOWN", notes="fusion_start")
    refs: list[str] = []

    series = None
    if observations and instrument:
        obs = observations.get(instrument.upper()) or observations.get(instrument)
        if obs and obs.get("values"):
            try:
                from god.research.drift import ObservationSeries

                vals = tuple(float(v) for v in obs["values"])
                series = ObservationSeries(name=instrument, values=vals)
            except Exception:
                series = None

    # --- 4E Drift ---
    if drift_engine is not None and series is not None and len(series.values) >= 4:
        try:
            mid = len(series.values) // 2
            from god.research.drift import ObservationSeries

            ref = ObservationSeries(name=series.name, values=series.values[:mid])
            cur = ObservationSeries(name=series.name, values=series.values[mid:])
            a = drift_engine.assess(ref, cur)
            ctx.drift_ref = a.assessment_id
            # map score/label if present
            score = getattr(a, "score", None)
            label = getattr(a, "label", None) or getattr(a, "drift_type", None)
            if label:
                ctx.drift_level = str(label).upper()
            elif score is not None:
                try:
                    s = abs(float(score))
                    ctx.drift_level = "HIGH" if s > 0.5 else ("MEDIUM" if s > 0.2 else "LOW")
                except (TypeError, ValueError):
                    ctx.drift_level = "UNKNOWN"
            else:
                ctx.drift_level = "UNKNOWN"
            refs.append(a.assessment_id)
        except Exception as exc:
            ctx.notes += f";drift_error:{type(exc).__name__}"
            ctx.drift_level = "UNKNOWN"
    elif drift_engine is None:
        ctx.drift_level = None  # truly unavailable
    else:
        ctx.drift_level = "UNKNOWN"

    # --- 4E Regime ---
    if regime_engine is not None and series is not None and len(series.values) >= 3:
        try:
            r = regime_engine.classify(series)
            ctx.regime_ref = r.regime_id
            label = getattr(r, "label", None) or getattr(r, "regime_type", None)
            if label is not None:
                ctx.regime_label = getattr(label, "value", str(label))
            else:
                ctx.regime_label = "UNKNOWN"
            refs.append(r.regime_id)
        except Exception as exc:
            ctx.notes += f";regime_error:{type(exc).__name__}"
            ctx.regime_label = "UNKNOWN"
    else:
        if regime_engine is None:
            ctx.regime_label = None
        else:
            ctx.regime_label = "UNKNOWN"

    # --- 4D Reality gap (optional synthetic expected vs last obs — only if values exist) ---
    if reality_engine is not None and series is not None and len(series.values) >= 2:
        try:
            from god.research.reality import GapDimension, MetricObservation

            exp_v = float(series.values[0])
            obs_v = float(series.values[-1])
            # critical if relative move large — descriptive flag, not trade law
            rel = abs(obs_v - exp_v) / (abs(exp_v) + 1e-12)
            g = reality_engine.record_gap(
                dimension=GapDimension.OBSERVATION_GAP,
                expected=MetricObservation(name=instrument or "x", value=exp_v),
                observed=MetricObservation(name=instrument or "x", value=obs_v),
            )
            ctx.reality_gap_ref = g.gap_id
            ctx.reality_gap_critical = bool(rel > 0.1)
            refs.append(g.gap_id)
        except Exception as exc:
            ctx.notes += f";reality_error:{type(exc).__name__}"
            ctx.reality_gap_critical = False
    else:
        ctx.reality_gap_critical = False

    # --- 4F Policy ---
    if policy_engine is not None:
        try:
            from god.policy import HealthFlag, PolicyEvidenceBundle

            bundle = PolicyEvidenceBundle(
                system_health=HealthFlag.HEALTHY,
                data_quality="VALID" if series is not None else "INSUFFICIENT_DATA",
                bridge_health=HealthFlag.HEALTHY,
                execution_health=HealthFlag.HEALTHY,
                drift_refs=[ctx.drift_ref] if ctx.drift_ref else [],
                reality_gap_refs=[ctx.reality_gap_ref] if ctx.reality_gap_ref else [],
                uncertainty="HIGH"
                if (ctx.drift_level or "").upper() in ("HIGH", "SEVERE")
                else "LOW",
            )
            d = policy_engine.evaluate(bundle)
            ctx.policy_permission = d.permission.value
            ctx.policy_ref = d.decision_id
            refs.append(d.decision_id)
        except Exception as exc:
            ctx.notes += f";policy_error:{type(exc).__name__}"
            ctx.policy_permission = "UNKNOWN"
    else:
        ctx.policy_permission = "UNKNOWN"

    # --- Capital safety state (evidence only) ---
    if capital_engine is not None:
        try:
            ctx.capital_state = str(capital_engine.state.value)
        except Exception:
            ctx.capital_state = "UNKNOWN"
    else:
        ctx.capital_state = None

    # uncertainty aggregate
    if (ctx.drift_level or "").upper() in ("HIGH", "SEVERE") or ctx.reality_gap_critical:
        ctx.uncertainty = "HIGH"
    elif ctx.policy_permission == "UNKNOWN" or ctx.drift_level == "UNKNOWN":
        ctx.uncertainty = "UNKNOWN"
    elif ctx.policy_permission == "ALLOW" and (ctx.drift_level or "LOW") in ("LOW", None):
        ctx.uncertainty = "LOW"
    else:
        ctx.uncertainty = "MEDIUM"

    ctx.evidence_refs = refs
    ctx.provenance = build_loop_provenance(
        {"refs": refs, "drift": ctx.drift_level, "regime": ctx.regime_label}
    )
    ctx.notes = (ctx.notes or "ok").lstrip(";")
    return ctx


def apply_evidence_to_status(
    *,
    base_status: str,
    evidence: EvidenceContext,
) -> tuple[str, str]:
    """
    Adjust attention status from fused evidence.
    Returns (AttentionStatus value, reason).
    Fail-closed: UNKNOWN/BLOCK do not become SELECTED.
    """
    perm = (evidence.policy_permission or "UNKNOWN").upper()
    if perm in ("BLOCK", "PAUSE"):
        return "BLOCKED", f"policy={perm}"
    if perm == "UNKNOWN":
        return "UNKNOWN", "policy=UNKNOWN"
    if (evidence.drift_level or "").upper() in ("HIGH", "SEVERE"):
        if base_status in ("SELECTED", "STILL_VALID"):
            return "DEGRADED", f"drift={evidence.drift_level}"
    if evidence.reality_gap_critical:
        if base_status in ("SELECTED", "STILL_VALID"):
            return "DEGRADED", "reality_gap_critical"
    if perm == "RESTRICT":
        return "SELECTED", "policy=RESTRICT"  # attention ok, restricted
    if perm == "ALLOW":
        return "SELECTED", "policy=ALLOW"
    return "UNKNOWN", "default"
