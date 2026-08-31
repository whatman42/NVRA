"""Integrity-verified rollback — never restores corrupt/incompatible artifacts.

Fail-closed. Auditable. Restart-safe. Never enables LIVE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .lifecycle import verify_artifact_integrity, load_with_integrity
from .manifest import load_manifest, verify_manifest_against_disk, save_manifest
from .registry import ModelRegistry


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SafeRollbackResult:
    success: bool
    reason: str = ""
    restored_id: str = ""
    restored_version: str = ""
    demoted_id: str = ""
    demoted_version: str = ""
    integrity_status: str = ""
    prefer_no_trade: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "reason": self.reason,
            "restored_id": self.restored_id,
            "restored_version": self.restored_version,
            "demoted_id": self.demoted_id,
            "demoted_version": self.demoted_version,
            "integrity_status": self.integrity_status,
            "prefer_no_trade": self.prefer_no_trade,
            "details": dict(self.details),
        }


def safe_rollback(
    registry: ModelRegistry,
    *,
    performance_collapse: bool = False,
    abnormal_drift: bool = False,
    calibration_failure: bool = False,
    runtime_failure: bool = False,
    resource_failure: bool = False,
    instability: bool = False,
    audit: Any = None,
) -> SafeRollbackResult:
    """Rollback only to integrity-verified previous champion. Fail-closed."""
    triggers = {
        "performance_collapse": performance_collapse,
        "abnormal_drift": abnormal_drift,
        "calibration_failure": calibration_failure,
        "runtime_failure": runtime_failure,
        "resource_failure": resource_failure,
        "instability": instability,
    }
    if not any(triggers.values()):
        return SafeRollbackResult(success=False, reason="no_rollback_trigger")

    champ = registry.champion()
    prev = registry.previous_champion()
    if prev is None:
        return SafeRollbackResult(
            success=False,
            reason="no_previous_champion",
            demoted_id=champ.model_id if champ else "",
            demoted_version=champ.model_version if champ else "",
            prefer_no_trade=True,
        )

    irep = verify_artifact_integrity(registry.root, prev.model_id, prev.model_version)
    if not irep.ok:
        return SafeRollbackResult(
            success=False,
            reason=f"previous_integrity_failed:{irep.status}",
            demoted_id=champ.model_id if champ else "",
            demoted_version=champ.model_version if champ else "",
            integrity_status=irep.status,
            prefer_no_trade=True,
            details={"integrity_reasons": list(irep.reasons)},
        )

    mok, mreason, _ = verify_manifest_against_disk(registry.root, prev.model_id, prev.model_version)
    if not mok and mreason not in ("manifest_missing_or_corrupt",):
        return SafeRollbackResult(
            success=False,
            reason=f"previous_manifest_failed:{mreason}",
            integrity_status=irep.status,
            prefer_no_trade=True,
        )

    model, _, bundle, load_rep = load_with_integrity(
        registry.root, prev.model_id, prev.model_version
    )
    if model is None or not load_rep.ok:
        return SafeRollbackResult(
            success=False,
            reason=f"previous_load_failed:{load_rep.status}",
            integrity_status=load_rep.status,
            prefer_no_trade=True,
        )

    demoted_id = champ.model_id if champ else ""
    demoted_ver = champ.model_version if champ else ""
    if champ is not None:
        for r in registry._records:
            if r.model_id == champ.model_id and r.model_version == champ.model_version:
                r.status = "rolled_back"
                break
    restored = None
    for r in registry._records:
        if r.model_id == prev.model_id and r.model_version == prev.model_version:
            r.status = "champion"
            restored = r
            break
    if restored is None:
        return SafeRollbackResult(success=False, reason="previous_record_missing", prefer_no_trade=True)

    registry._save()

    man = load_manifest(registry.root, restored.model_id, restored.model_version)
    if man is not None:
        man.status = "champion"
        man.promoted_at = _utc_now()
        man.rollback_from_id = demoted_id
        man.rollback_from_version = demoted_ver
        man.rollback_reason = ",".join(k for k, v in triggers.items() if v)
        try:
            save_manifest(registry.root, man)
        except OSError:
            pass

    if audit is not None:
        try:
            audit.record(
                "rollback",
                model_id=restored.model_id,
                model_version=restored.model_version,
                outcome="success",
                detail={
                    "from": f"{demoted_id}@{demoted_ver}",
                    "triggers": [k for k, v in triggers.items() if v],
                    "integrity": irep.status,
                },
            )
        except Exception:
            pass

    return SafeRollbackResult(
        success=True,
        reason="rolled_back_integrity_verified",
        restored_id=restored.model_id,
        restored_version=restored.model_version,
        demoted_id=demoted_id,
        demoted_version=demoted_ver,
        integrity_status="ok",
    )
