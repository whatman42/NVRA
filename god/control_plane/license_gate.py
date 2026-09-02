"""License Gate — operational entrypoints must pass before runtime."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .fallback import FallbackStore, OfflineDecision, evaluate_offline
from .store import ControlPlaneStore

@dataclass
class GateResult:
    allowed: bool
    reason: str
    offline: bool = False
    decision: Optional[OfflineDecision] = None

class LicenseGate:
    def __init__(self, store: Optional[ControlPlaneStore] = None, fallback: Optional[FallbackStore] = None, *, require_license: bool = True) -> None:
        self.store = store
        self.fallback = fallback
        self.require_license = require_license

    def check(self, *, license_id: str = "", cloud_available: bool = True) -> GateResult:
        if not self.require_license:
            return GateResult(True, "gate_disabled_dev_only")
        if cloud_available and self.store and license_id:
            ok, reason = self.store.verify_license(license_id)
            if ok:
                return GateResult(True, "license_ok")
            if reason in {"revoked", "disabled", "expired"}:
                return GateResult(False, reason)
        if self.fallback:
            state, why = self.fallback.load_and_verify()
            decision = evaluate_offline(state, why)
            if decision.allowed:
                return GateResult(True, decision.reason, offline=True, decision=decision)
            return GateResult(False, decision.reason, offline=True, decision=decision)
        return GateResult(False, "license_required")
