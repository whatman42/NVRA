"""Crash/restart recovery for ML state — champion reload + consistency checks.

Fail-closed: invalid/corrupt champion → no model, prefer NO_TRADE / SAFE_ONLY.
Recovery chooses previous valid champion when possible. Atomic + auditable.
Never auto-promotes. Never enables LIVE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .lifecycle import verify_artifact_integrity, load_with_integrity
from .manifest import load_manifest, verify_manifest_against_disk
from .persist import load_trained_model_safe
from .registry import ModelRecord, ModelRegistry
from .train import TrainedModel


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RecoveryResult:
    success: bool
    status: str  # restored | no_champion | corrupt | incomplete | inconsistent | error | safe_only
    model_id: str = ""
    model_version: str = ""
    reasons: list[str] = field(default_factory=list)
    restored_at: str = ""
    prefer_no_trade: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "reasons": list(self.reasons),
            "restored_at": self.restored_at,
            "prefer_no_trade": self.prefer_no_trade,
            "details": dict(self.details),
        }


def _try_load_valid(
    registry: ModelRegistry,
    model_id: str,
    model_version: str,
) -> tuple[Optional[TrainedModel], str, list[str]]:
    """Load only if integrity + safe load pass. Returns (model, status, reasons)."""
    reasons: list[str] = []
    irep = verify_artifact_integrity(registry.root, model_id, model_version)
    if not irep.ok:
        reasons.append(f"integrity:{irep.status}")
        reasons.extend(irep.reasons)
        return None, irep.status, reasons

    mok, mreason, _ = verify_manifest_against_disk(registry.root, model_id, model_version)
    if not mok and mreason not in ("manifest_missing_or_corrupt",):
        reasons.append(f"manifest:{mreason}")
        return None, "corrupt", reasons

    model, cal, bundle, load_rep = load_with_integrity(registry.root, model_id, model_version)
    if model is None or not load_rep.ok:
        reasons.append(f"load:{load_rep.status}")
        reasons.extend(load_rep.reasons)
        return None, load_rep.status or "corrupt", reasons

    # Calibration artifact soft-check: missing is OK; corrupt payload flagged
    if bundle is not None and bundle.calibration:
        cal = bundle.calibration
        if isinstance(cal, dict) and cal.get("status") in ("corrupt", "invalid", "INVALID"):
            reasons.append("calibration_corrupt")
            return None, "corrupt", reasons

    return model, "ok", reasons


def recover_champion(
    registry: ModelRegistry,
    *,
    try_previous_on_corrupt: bool = True,
    audit: Any = None,
) -> tuple[RecoveryResult, Optional[TrainedModel]]:
    """Load champion safely after restart. Optionally fall back to previous valid."""
    champ = registry.champion()
    if champ is None:
        result = RecoveryResult(
            success=False,
            status="no_champion",
            reasons=["registry_has_no_champion"],
            restored_at=_utc_now(),
            prefer_no_trade=True,
        )
        if audit is not None:
            try:
                audit.record("recovery", outcome="failed", detail=result.to_dict())
            except Exception:
                pass
        return result, None

    model, st, reasons = _try_load_valid(registry, champ.model_id, champ.model_version)
    if st == "ok" and model is not None:
        result = RecoveryResult(
            success=True,
            status="restored",
            model_id=champ.model_id,
            model_version=champ.model_version,
            restored_at=_utc_now(),
        )
        if audit is not None:
            try:
                audit.record(
                    "recovery",
                    model_id=champ.model_id,
                    model_version=champ.model_version,
                    outcome="success",
                    detail=result.to_dict(),
                )
            except Exception:
                pass
        return result, model

    # Incomplete / corrupt champion path
    if st in ("missing",):
        reasons.append("incomplete_artifact")

    if try_previous_on_corrupt:
        prev = registry.previous_champion()
        if prev is not None:
            m2, st2, r2 = _try_load_valid(registry, prev.model_id, prev.model_version)
            if st2 == "ok" and m2 is not None:
                for r in registry.list_models():
                    if r.model_id == champ.model_id and r.model_version == champ.model_version:
                        r.status = "rolled_back"
                    elif r.model_id == prev.model_id and r.model_version == prev.model_version:
                        r.status = "champion"
                registry._save()
                result = RecoveryResult(
                    success=True,
                    status="restored",
                    model_id=prev.model_id,
                    model_version=prev.model_version,
                    reasons=reasons + ["fell_back_to_previous_champion"] + r2,
                    restored_at=_utc_now(),
                    details={"demoted": f"{champ.model_id}@{champ.model_version}"},
                )
                if audit is not None:
                    try:
                        audit.record(
                            "recovery",
                            model_id=prev.model_id,
                            model_version=prev.model_version,
                            outcome="success",
                            detail=result.to_dict(),
                        )
                    except Exception:
                        pass
                return result, m2
            reasons.append(f"previous_load_{st2}")
            reasons.extend(r2)

    result = RecoveryResult(
        success=False,
        status="safe_only" if st in ("corrupt", "missing", "incomplete") else "corrupt",
        model_id=champ.model_id,
        model_version=champ.model_version,
        reasons=reasons,
        restored_at=_utc_now(),
        prefer_no_trade=True,
    )
    if audit is not None:
        try:
            audit.record(
                "recovery",
                model_id=champ.model_id,
                model_version=champ.model_version,
                outcome="failed",
                detail=result.to_dict(),
            )
        except Exception:
            pass
    return result, None


def recover_startup(
    registry: ModelRegistry,
    *,
    audit: Any = None,
) -> tuple[RecoveryResult, Optional[TrainedModel]]:
    """Full startup recovery: consistency + champion recovery + incomplete cleanup signals."""
    consistency = check_state_consistency(registry)
    if not consistency["consistent"] and "multiple_champions" in str(consistency.get("issues", [])):
        # Fail-closed: do not pick arbitrarily
        result = RecoveryResult(
            success=False,
            status="inconsistent",
            reasons=list(consistency.get("issues") or ["inconsistent_state"]),
            restored_at=_utc_now(),
            prefer_no_trade=True,
            details=consistency,
        )
        if audit is not None:
            try:
                audit.record("recovery", outcome="failed", detail=result.to_dict())
            except Exception:
                pass
        return result, None

    return recover_champion(registry, try_previous_on_corrupt=True, audit=audit)


def check_state_consistency(registry: ModelRegistry) -> dict[str, Any]:
    """Verify at most one champion; flag inconsistencies."""
    champs = [r for r in registry.list_models() if r.status == "champion"]
    issues: list[str] = []
    if len(champs) == 0:
        issues.append("no_champion")
    elif len(champs) > 1:
        issues.append(f"multiple_champions:{len(champs)}")
    return {
        "consistent": len(issues) == 0,
        "champion_count": len(champs),
        "issues": issues,
        "checked_at": _utc_now(),
    }
