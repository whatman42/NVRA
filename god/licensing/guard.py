"""Startup license/device guard.
Configured deployments fail closed; unconfigured development builds remain explicit LOCAL_ONLY."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .device import load_or_create_identity, DeviceLicenseClient
from .http_client import HttpsDeviceLicenseClient

@dataclass(frozen=True)
class DeviceGuardResult:
    allowed: bool
    status: str
    device_id: str
    account_id: str

def check_device(account_id: str, identity_path: str | Path, service_url: str = "") -> DeviceGuardResult:
    identity = load_or_create_identity(identity_path)
    if not service_url:
        return DeviceGuardResult(True, "LOCAL_ONLY", identity.device_id, account_id)
    client: DeviceLicenseClient = HttpsDeviceLicenseClient(service_url)
    try:
        result = client.check(account_id, identity)
    except Exception as exc:
        return DeviceGuardResult(False, f"LICENSE_SERVICE_ERROR:{type(exc).__name__}", identity.device_id, account_id)
    allowed = bool(result.get("ok")) and str(result.get("status", "ACTIVE")).upper() not in {"REVOKED", "DENIED", "EXPIRED"}
    return DeviceGuardResult(allowed, str(result.get("status", "UNKNOWN")), identity.device_id, account_id)
