"""Deterministic fail-closed policy composition.

Higher safety evidence always dominates.
NO SILENT ALLOW. Missing critical evidence ≠ healthy.
"""

from __future__ import annotations

from .models import HealthFlag, Permission, PolicyEvidenceBundle


def compose(bundle: PolicyEvidenceBundle) -> tuple[Permission, list[str], list[str]]:
    """
    Returns (permission, reasons, composition_trace).

    Priority (highest first):
      SYSTEM > DATA > BRIDGE/EXEC > RCA/REALITY > DRIFT/REGIME > STRATEGY > DEFAULT

    ALLOW requires explicit positive path: all critical health HEALTHY/VALID
    and no higher-priority restrictive signal.
    """
    reasons: list[str] = []
    trace: list[str] = []

    rank = {
        Permission.ALLOW: 0,
        Permission.UNKNOWN: 1,
        Permission.RESTRICT: 2,
        Permission.PAUSE: 3,
        Permission.BLOCK: 4,
    }
    current = Permission.ALLOW  # will be raised; start optimistic then fail-closed checks

    def raise_to(perm: Permission, reason: str, layer: str) -> None:
        nonlocal current
        if rank[perm] > rank[current]:
            current = perm
        reasons.append(reason)
        trace.append(f"{layer}:{perm.value}:{reason}")

    # --- 1 SYSTEM ---
    if bundle.system_health in (HealthFlag.FAILED, HealthFlag.UNAVAILABLE):
        raise_to(Permission.BLOCK, f"system_health={bundle.system_health.value}", "SYSTEM")
    elif bundle.system_health == HealthFlag.DEGRADED:
        raise_to(Permission.PAUSE, f"system_health={bundle.system_health.value}", "SYSTEM")
    elif bundle.system_health == HealthFlag.UNKNOWN:
        raise_to(Permission.UNKNOWN, "system_health=UNKNOWN", "SYSTEM")
    else:
        trace.append("SYSTEM:HEALTHY")

    # --- 2 DATA ---
    dq = (bundle.data_quality or "UNKNOWN").upper()
    if dq in ("INVALID", "CORRUPTED"):
        raise_to(Permission.BLOCK, f"data_quality={dq}", "DATA")
    elif dq in ("INSUFFICIENT_DATA", "UNAVAILABLE", "UNKNOWN", ""):
        raise_to(Permission.UNKNOWN, f"data_quality={dq or 'UNKNOWN'}", "DATA")
    elif dq == "DEGRADED":
        raise_to(Permission.RESTRICT, f"data_quality={dq}", "DATA")
    else:
        trace.append(f"DATA:{dq}")

    # --- 3 BRIDGE / EXEC ---
    for label, flag in (
        ("bridge_health", bundle.bridge_health),
        ("execution_health", bundle.execution_health),
    ):
        if flag in (HealthFlag.FAILED, HealthFlag.UNAVAILABLE):
            raise_to(Permission.BLOCK, f"{label}={flag.value}", "BRIDGE_EXEC")
        elif flag == HealthFlag.DEGRADED:
            raise_to(Permission.PAUSE, f"{label}={flag.value}", "BRIDGE_EXEC")
        elif flag == HealthFlag.UNKNOWN:
            raise_to(Permission.UNKNOWN, f"{label}=UNKNOWN", "BRIDGE_EXEC")
        else:
            trace.append(f"BRIDGE_EXEC:{label}=HEALTHY")

    # --- 4 RCA / REALITY (cautionary; does not alone BLOCK) ---
    if bundle.rca_refs:
        raise_to(
            Permission.RESTRICT,
            f"rca_refs_present={len(bundle.rca_refs)}",
            "RCA_REALITY",
        )
    if bundle.reality_gap_refs:
        raise_to(
            Permission.RESTRICT,
            f"reality_gap_refs_present={len(bundle.reality_gap_refs)}",
            "RCA_REALITY",
        )
    if not bundle.rca_refs and not bundle.reality_gap_refs:
        trace.append("RCA_REALITY:none")

    # --- 5 DRIFT / REGIME / UNCERTAINTY ---
    unc = (bundle.uncertainty or "UNKNOWN").upper()
    if unc in ("HIGH", "INSUFFICIENT_DATA"):
        raise_to(Permission.RESTRICT, f"uncertainty={unc}", "DRIFT_REGIME")
    if bundle.drift_refs:
        raise_to(
            Permission.RESTRICT,
            f"drift_refs_present={len(bundle.drift_refs)}",
            "DRIFT_REGIME",
        )
    if not bundle.drift_refs and unc not in ("HIGH", "INSUFFICIENT_DATA"):
        trace.append(f"DRIFT_REGIME:uncertainty={unc}")

    # --- 6 STRATEGY lifecycle (read-only) ---
    sls = (bundle.strategy_lifecycle_state or "").upper()
    if sls in ("RETIRED", "REJECTED"):
        raise_to(Permission.BLOCK, f"strategy_lifecycle={sls}", "STRATEGY")
    elif sls == "DEGRADED":
        raise_to(Permission.RESTRICT, f"strategy_lifecycle={sls}", "STRATEGY")
    elif sls:
        trace.append(f"STRATEGY:lifecycle={sls}")
    else:
        trace.append("STRATEGY:lifecycle_absent")

    # --- 7 DEFAULT / explicit positive path ---
    critical_ok = (
        bundle.system_health == HealthFlag.HEALTHY
        and dq == "VALID"
        and bundle.bridge_health == HealthFlag.HEALTHY
        and bundle.execution_health == HealthFlag.HEALTHY
    )

    if current == Permission.ALLOW:
        if critical_ok:
            trace.append("DEFAULT:explicit_positive_path→ALLOW")
            if not reasons:
                reasons.append("explicit_positive_health_path")
            return Permission.ALLOW, reasons, trace
        # incomplete critical health should never stay ALLOW
        raise_to(Permission.UNKNOWN, "critical_health_incomplete", "DEFAULT")

    if current == Permission.UNKNOWN and not critical_ok:
        if "critical_health_incomplete" not in reasons:
            reasons.append("critical_health_incomplete")
            trace.append("DEFAULT:UNKNOWN:critical_health_incomplete")

    return current, reasons, trace
