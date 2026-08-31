"""Administrator / license / device models — no plaintext secrets."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LicenseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"


class AdminStatus(str, Enum):
    ADMIN_ACTIVE = "ADMIN_ACTIVE"
    ADMIN_LOCKED = "ADMIN_LOCKED"
    ADMIN_SUSPENDED = "ADMIN_SUSPENDED"


@dataclass
class AdminIdentity:
    admin_id: str
    username: str
    display_name: str
    status: AdminStatus
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "admin_id": self.admin_id,
            "username": self.username,
            "display_name": self.display_name,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdminIdentity":
        return cls(
            admin_id=str(data["admin_id"]),
            username=str(data["username"]),
            display_name=str(data.get("display_name") or data["username"]),
            status=AdminStatus(str(data.get("status", AdminStatus.ADMIN_ACTIVE.value))),
            created_at=str(data["created_at"]),
        )

    @staticmethod
    def create(username: str, display_name: Optional[str] = None) -> "AdminIdentity":
        return AdminIdentity(
            admin_id=str(uuid.uuid4()),
            username=username.strip(),
            display_name=(display_name or username).strip(),
            status=AdminStatus.ADMIN_ACTIVE,
            created_at=utc_now(),
        )


@dataclass
class ClientRecord:
    user_id: str
    username: str
    display_name: str
    status: str = "ACTIVE"  # ACTIVE | LOCKED | SUSPENDED | REVOKED
    created_at: str = field(default_factory=utc_now)
    failed_logins: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "status": self.status,
            "created_at": self.created_at,
            "failed_logins": self.failed_logins,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClientRecord":
        return cls(
            user_id=str(data["user_id"]),
            username=str(data["username"]),
            display_name=str(data.get("display_name") or data["username"]),
            status=str(data.get("status", "ACTIVE")),
            created_at=str(data.get("created_at") or utc_now()),
            failed_logins=int(data.get("failed_logins") or 0),
        )


@dataclass
class LicenseRecord:
    license_id: str
    user_id: str
    username: str
    issued_at: str
    expires_at: Optional[str]  # None = NO EXPIRY
    status: LicenseStatus
    version: int = 1
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "license_id": self.license_id,
            "user_id": self.user_id,
            "username": self.username,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "status": self.status.value,
            "version": self.version,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LicenseRecord":
        return cls(
            license_id=str(data["license_id"]),
            user_id=str(data["user_id"]),
            username=str(data["username"]),
            issued_at=str(data["issued_at"]),
            expires_at=data.get("expires_at"),
            status=LicenseStatus(str(data.get("status", LicenseStatus.ACTIVE.value))),
            version=int(data.get("version") or 1),
            signature=str(data.get("signature") or ""),
        )

    def is_trading_allowed(self, now: Optional[datetime] = None) -> bool:
        if self.status in (LicenseStatus.REVOKED, LicenseStatus.SUSPENDED):
            return False
        if self.status == LicenseStatus.EXPIRED:
            return False
        if self.expires_at:
            try:
                exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            except ValueError:
                return False
            current = now or datetime.now(timezone.utc)
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            if current > exp:
                return False
        return self.status == LicenseStatus.ACTIVE


@dataclass
class DeviceRecord:
    device_id: str
    user_id: str
    label: str
    os_name: str
    app_version: str
    last_seen: str
    status: str = "ACTIVE"  # ACTIVE | REVOKED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "user_id": self.user_id,
            "label": self.label,
            "os_name": self.os_name,
            "app_version": self.app_version,
            "last_seen": self.last_seen,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceRecord":
        return cls(
            device_id=str(data["device_id"]),
            user_id=str(data["user_id"]),
            label=str(data.get("label") or ""),
            os_name=str(data.get("os_name") or ""),
            app_version=str(data.get("app_version") or ""),
            last_seen=str(data.get("last_seen") or utc_now()),
            status=str(data.get("status") or "ACTIVE"),
        )
