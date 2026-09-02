"""Optional License Gate hook. NVRA_LICENSE_GATE=1 to enforce."""
from __future__ import annotations
import os
from typing import Optional
from .license_gate import GateResult, LicenseGate

def gate_enabled() -> bool:
    return os.environ.get("NVRA_LICENSE_GATE", "").strip() in {"1", "true", "TRUE", "yes"}

def smoke_exempt(argv: list[str] | None = None) -> bool:
    if os.environ.get("NVRA_LICENSE_GATE_SMOKE_EXEMPT", "1").strip() in {"1", "true", "TRUE"}:
        args = argv or []
        return any(a in {"--version", "--health", "--check-config", "--help", "-h"} for a in args)
    return False

def enforce_license_gate(*, license_id: str = "", cloud_available: bool = True, gate: Optional[LicenseGate] = None, argv: list[str] | None = None) -> GateResult:
    if not gate_enabled():
        return GateResult(True, "gate_not_enabled")
    if smoke_exempt(argv):
        return GateResult(True, "smoke_exempt")
    g = gate or LicenseGate(require_license=True)
    return g.check(license_id=license_id or os.environ.get("NVRA_LICENSE_ID", ""), cloud_available=cloud_available)
