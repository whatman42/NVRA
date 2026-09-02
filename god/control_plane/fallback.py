"""Local signed control-plane fallback — integrity-protected offline state."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .ed25519_license import sign_license_payload, verify_license_payload

FALLBACK_SCHEMA = 1


@dataclass
class SignedFallbackState:
    schema_version: int = FALLBACK_SCHEMA
    license_id: str = ""
    license_status: str = ""
    account_id: str = ""
    account_status: str = ""
    device_id: str = ""
    device_status: str = ""
    policy_hash: str = ""
    last_heartbeat_at: float = 0.0
    last_sync_at: float = 0.0
    last_known_time: float = 0.0
    grace_until: float = 0.0
    control_plane_snapshot_hash: str = ""
    paper_only: bool = True
    risk_ceiling_locked: bool = True
    signature: str = ""

    def payload_for_sign(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "license_id": self.license_id,
            "license_status": self.license_status,
            "account_id": self.account_id,
            "account_status": self.account_status,
            "device_id": self.device_id,
            "device_status": self.device_status,
            "policy_hash": self.policy_hash,
            "last_heartbeat_at": self.last_heartbeat_at,
            "last_sync_at": self.last_sync_at,
            "last_known_time": self.last_known_time,
            "grace_until": self.grace_until,
            "control_plane_snapshot_hash": self.control_plane_snapshot_hash,
            "paper_only": self.paper_only,
            "risk_ceiling_locked": self.risk_ceiling_locked,
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.payload_for_sign()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SignedFallbackState":
        return cls(
            schema_version=int(data.get("schema_version") or FALLBACK_SCHEMA),
            license_id=str(data.get("license_id") or ""),
            license_status=str(data.get("license_status") or ""),
            account_id=str(data.get("account_id") or ""),
            account_status=str(data.get("account_status") or ""),
            device_id=str(data.get("device_id") or ""),
            device_status=str(data.get("device_status") or ""),
            policy_hash=str(data.get("policy_hash") or ""),
            last_heartbeat_at=float(data.get("last_heartbeat_at") or 0),
            last_sync_at=float(data.get("last_sync_at") or 0),
            last_known_time=float(data.get("last_known_time") or 0),
            grace_until=float(data.get("grace_until") or 0),
            control_plane_snapshot_hash=str(data.get("control_plane_snapshot_hash") or ""),
            paper_only=bool(data.get("paper_only", True)),
            risk_ceiling_locked=bool(data.get("risk_ceiling_locked", True)),
            signature=str(data.get("signature") or ""),
        )


class FallbackStore:
    def __init__(self, path: Path, *, public_pem: bytes, private_pem: Optional[bytes] = None):
        self.path = Path(path)
        self.public_pem = public_pem
        self.private_pem = private_pem

    def sign_and_save(self, state: SignedFallbackState) -> SignedFallbackState:
        if not self.private_pem:
            raise PermissionError("private_key_required_to_write_fallback")
        state.last_known_time = max(state.last_known_time, time.time())
        state.signature = sign_license_payload(self.private_pem, state.payload_for_sign())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
        try:
            import os
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return state

    def load_and_verify(self) -> tuple[Optional[SignedFallbackState], str]:
        if not self.path.is_file():
            return None, "missing"
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, "corrupt"
        state = SignedFallbackState.from_dict(data)
        if not state.signature:
            return None, "unsigned"
        if not verify_license_payload(self.public_pem, state.payload_for_sign(), state.signature):
            return None, "bad_signature"
        return state, "ok"


@dataclass
class OfflineDecision:
    allowed: bool
    mode: str
    reason: str
    paper_only: bool = True
    live_trading: bool = False
    risk_ceiling_raise: bool = False


def evaluate_offline(
    state: Optional[SignedFallbackState],
    verify_reason: str,
    *,
    now: Optional[float] = None,
    grace_sec: float = 0.0,
) -> OfflineDecision:
    now = now if now is not None else time.time()
    if state is None:
        return OfflineDecision(False, "SAFE_MODE", f"fallback_{verify_reason}")
    if verify_reason != "ok":
        return OfflineDecision(False, "SAFE_MODE", f"fallback_{verify_reason}")
    if state.last_known_time and now + 1.0 < state.last_known_time:
        return OfflineDecision(False, "SAFE_MODE", "clock_rollback")
    if state.license_status in {"REVOKED", "DISABLED", "EXPIRED"}:
        return OfflineDecision(False, "LICENSE_BLOCKED", f"license_{state.license_status.lower()}")
    if state.account_status in {"REVOKED", "DISABLED"}:
        return OfflineDecision(False, "LICENSE_BLOCKED", f"account_{state.account_status.lower()}")
    if state.device_status in {"REVOKED", "DISABLED"}:
        return OfflineDecision(False, "SAFE_MODE", f"device_{state.device_status.lower()}")
    if grace_sec > 0 and state.last_sync_at:
        limit = state.last_sync_at + grace_sec
        if state.grace_until:
            limit = min(limit, state.grace_until)
        if now > limit:
            return OfflineDecision(False, "SAFE_MODE", "grace_exhausted")
    if not state.paper_only:
        return OfflineDecision(False, "SAFE_MODE", "paper_only_required")
    return OfflineDecision(True, "LIMITED_OFFLINE_PAPER", "valid_signed_fallback",
                           paper_only=True, live_trading=False, risk_ceiling_raise=False)


def snapshot_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
