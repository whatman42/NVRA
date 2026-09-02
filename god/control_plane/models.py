"""Control-plane entities — no secrets."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .roles import AccountStatus, DeviceStatus, LicenseStatus, Role


def _now() -> float:
    return time.time()


@dataclass
class Account:
    id: str
    username: str
    role: Role
    status: AccountStatus = AccountStatus.ACTIVE
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "username": self.username, "role": self.role.value,
            "status": self.status.value, "created_at": self.created_at, "updated_at": self.updated_at,
        }


@dataclass
class License:
    id: str
    account_id: str
    username: str
    status: LicenseStatus = LicenseStatus.ACTIVE
    issued_at: str = ""
    expires_at: Optional[str] = None
    signature: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "account_id": self.account_id, "username": self.username,
            "status": self.status.value, "issued_at": self.issued_at, "expires_at": self.expires_at,
            "signature": self.signature, "payload": dict(self.payload), "created_at": self.created_at,
        }


@dataclass
class Device:
    id: str
    account_id: str
    status: DeviceStatus = DeviceStatus.ACTIVE
    client_version: str = ""
    os_name: str = ""
    last_seen: float = field(default_factory=_now)
    hostname: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "account_id": self.account_id, "status": self.status.value,
            "client_version": self.client_version, "os_name": self.os_name,
            "last_seen": self.last_seen, "hostname": self.hostname,
        }


@dataclass
class Session:
    id: str
    account_id: str
    device_id: str
    token_hash: str
    expires_at: float
    revoked: bool = False
    created_at: float = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Heartbeat:
    id: str
    account_id: str
    device_id: str
    license_id: str
    client_version: str
    timestamp: float
    status: str
    state_hash: str
    runtime_status: str = "PAPER"
    safe_mode: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEvent:
    id: str
    actor: str
    action: str
    target: str
    result: str
    timestamp: float = field(default_factory=_now)
    request_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        bad = ("password", "secret", "token", "api_key", "private")
        d["details"] = {k: v for k, v in (self.details or {}).items() if not any(b in str(k).lower() for b in bad)}
        return d


def new_id() -> str:
    return uuid.uuid4().hex
