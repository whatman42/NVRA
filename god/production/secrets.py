"""Phase 6A — N.U.N.G. secret reference foundation. No raw secrets in config."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SecretStatus(str, Enum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SecretRef:
    """Reference by name only — never stores the secret value."""

    name: str
    status: SecretStatus = SecretStatus.UNKNOWN

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status.value}


class SecretRegistry:
    """
    Tracks secret *names* and presence flags only.
    Values are never stored, logged, or fingerprinted.
    """

    def __init__(self) -> None:
        self._refs: dict[str, SecretStatus] = {}

    def register_presence(self, name: str, present: bool) -> SecretRef:
        if not name or not str(name).strip():
            raise ValueError("empty_secret_name")
        status = SecretStatus.PRESENT if present else SecretStatus.MISSING
        self._refs[name] = status
        return SecretRef(name=name, status=status)

    def status_of(self, name: str) -> SecretStatus:
        return self._refs.get(name, SecretStatus.UNKNOWN)

    def require(self, name: str) -> SecretRef:
        st = self.status_of(name)
        if st != SecretStatus.PRESENT:
            return SecretRef(name=name, status=SecretStatus.MISSING)
        return SecretRef(name=name, status=SecretStatus.PRESENT)

    def list_refs(self) -> list[SecretRef]:
        return [SecretRef(name=n, status=s) for n, s in sorted(self._refs.items())]
