"""Cryptographic device identity and one-active-device license client contract."""
from __future__ import annotations
import hashlib, json, os, platform, secrets
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

@dataclass(frozen=True)
class DeviceIdentity:
    installation_id: str
    device_id: str
    public_fingerprint: str
    created_at: str


def _machine_material() -> str:
    candidates = [platform.node(), platform.system(), platform.machine(), os.environ.get("COMPUTERNAME", "")]
    try:
        candidates.append(Path("/etc/machine-id").read_text(encoding="utf-8").strip())
    except OSError:
        pass
    return "|".join(candidates)


def load_or_create_identity(path: str | Path) -> DeviceIdentity:
    p = Path(path)
    if p.exists():
        return DeviceIdentity(**json.loads(p.read_text(encoding="utf-8")))
    installation = secrets.token_hex(16)
    material = f"{installation}|{_machine_material()}|{secrets.token_hex(16)}"
    device_id = hashlib.sha256(material.encode()).hexdigest()[:32]
    fingerprint = hashlib.sha256(_machine_material().encode()).hexdigest()
    from datetime import datetime, timezone
    identity = DeviceIdentity(installation, device_id, fingerprint, datetime.now(timezone.utc).isoformat())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(identity), indent=2), encoding="utf-8")
    return identity

class DeviceLicenseClient:
    """Transport-neutral license service contract.

    A deployment may supply register/revoke/check callables backed by HTTPS.
    No remote license server is assumed or fabricated by the desktop client.
    """
    def __init__(self, register: Callable | None = None, check: Callable | None = None, revoke: Callable | None = None):
        self._register = register
        self._check = check
        self._revoke = revoke
    def register_device(self, account_id: str, identity: DeviceIdentity) -> dict:
        if not self._register:
            return {"ok": False, "status": "LICENSE_SERVICE_NOT_CONFIGURED"}
        return dict(self._register(account_id, asdict(identity)))
    def check(self, account_id: str, identity: DeviceIdentity) -> dict:
        if not self._check:
            return {"ok": False, "status": "LICENSE_SERVICE_NOT_CONFIGURED"}
        return dict(self._check(account_id, asdict(identity)))
    def revoke(self, account_id: str, device_id: str) -> dict:
        if not self._revoke:
            return {"ok": False, "status": "LICENSE_SERVICE_NOT_CONFIGURED"}
        return dict(self._revoke(account_id, device_id))
