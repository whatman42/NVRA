"""Evidence aggregation for discovery — refs only, no synthetic production path."""

from __future__ import annotations

from typing import Any, Optional


def collect_strategy_refs(strategy_registry: Any) -> list[dict[str, str]]:
    """Read-only list of strategy ids + lifecycle from 4C registry if present."""
    if strategy_registry is None:
        return []
    out: list[dict[str, str]] = []
    try:
        all_s = strategy_registry.list_all()
        for s in all_s:
            out.append(
                {
                    "strategy_id": s.strategy_id,
                    "lifecycle": getattr(
                        s.lifecycle_state, "value", str(s.lifecycle_state)
                    ),
                }
            )
    except Exception:
        return []
    return out


def policy_permission(
    policy_engine: Any,
    *,
    strategy_lifecycle: Optional[str] = None,
    evidence_refs: Optional[list[str]] = None,
) -> tuple[str, Optional[str]]:
    """
    Returns (permission_value, decision_id).
    If engine unavailable → UNKNOWN (no synthetic ALLOW).
    """
    if policy_engine is None:
        return "UNKNOWN", None
    try:
        from god.policy import HealthFlag, PolicyEvidenceBundle

        bundle = PolicyEvidenceBundle(
            system_health=HealthFlag.HEALTHY,
            data_quality="VALID",
            bridge_health=HealthFlag.HEALTHY,
            execution_health=HealthFlag.HEALTHY,
            strategy_lifecycle_state=strategy_lifecycle,
            evidence_refs=list(evidence_refs or []),
            uncertainty="LOW",
        )
        d = policy_engine.evaluate(bundle)
        return d.permission.value, d.decision_id
    except Exception:
        return "UNKNOWN", None
