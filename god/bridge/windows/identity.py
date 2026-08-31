"""Stable terminal identity + ambiguity handling.

Never silently picks among multiple MT4/MT5 candidates.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from god.bridge.models import Platform, TerminalInstance


class IdentityStatus(str, Enum):
    UNIQUE = "UNIQUE"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class TerminalIdentity:
    """Stable identity for one terminal installation/instance."""

    identity_id: str
    platform: Platform
    executable_path: Optional[str] = None
    data_path: Optional[str] = None
    experts_path: Optional[str] = None
    version: Optional[str] = None
    process_id: Optional[int] = None
    fingerprint: str = ""
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def from_instance(t: TerminalInstance) -> "TerminalIdentity":
        fp = _fingerprint(t)
        return TerminalIdentity(
            identity_id=t.terminal_id,
            platform=t.platform,
            executable_path=t.executable_path,
            data_path=t.data_path,
            experts_path=t.experts_path,
            version=t.version,
            process_id=t.process_id,
            fingerprint=fp,
            metadata=dict(t.metadata or {}),
        )

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "platform": self.platform.value if isinstance(self.platform, Platform) else str(self.platform),
            "executable_path": self.executable_path,
            "data_path": self.data_path,
            "experts_path": self.experts_path,
            "version": self.version,
            "process_id": self.process_id,
            "fingerprint": self.fingerprint,
            "metadata": dict(self.metadata),
        }


@dataclass
class IdentityResolution:
    """Result of resolving terminal targets."""

    status: IdentityStatus
    candidates: list[TerminalIdentity] = field(default_factory=list)
    selected: Optional[TerminalIdentity] = None
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "candidates": [c.to_dict() for c in self.candidates],
            "selected": self.selected.to_dict() if self.selected else None,
            "message": self.message,
        }


def resolve_identities(
    instances: Sequence[TerminalInstance],
    *,
    platform: Optional[Platform | str] = None,
    explicit_id: Optional[str] = None,
    explicit_fingerprint: Optional[str] = None,
) -> IdentityResolution:
    """Resolve candidates; require explicit selection when ambiguous."""
    idents = [TerminalIdentity.from_instance(t) for t in instances]
    if platform is not None:
        plat = platform if isinstance(platform, Platform) else Platform(platform)
        idents = [i for i in idents if i.platform == plat]

    if not idents:
        return IdentityResolution(
            status=IdentityStatus.NOT_FOUND,
            message="no terminal candidates",
        )

    if explicit_id:
        match = [i for i in idents if i.identity_id == explicit_id]
        if len(match) == 1:
            return IdentityResolution(
                status=IdentityStatus.UNIQUE,
                candidates=idents,
                selected=match[0],
                message="explicit identity_id",
            )
        if not match:
            return IdentityResolution(
                status=IdentityStatus.NOT_FOUND,
                candidates=idents,
                message=f"identity_id not found: {explicit_id}",
            )

    if explicit_fingerprint:
        match = [i for i in idents if i.fingerprint == explicit_fingerprint]
        if len(match) == 1:
            return IdentityResolution(
                status=IdentityStatus.UNIQUE,
                candidates=idents,
                selected=match[0],
                message="explicit fingerprint",
            )

    by_fp: dict[str, TerminalIdentity] = {}
    for i in idents:
        by_fp.setdefault(i.fingerprint, i)
    unique = list(by_fp.values())

    if len(unique) == 1:
        return IdentityResolution(
            status=IdentityStatus.UNIQUE,
            candidates=unique,
            selected=unique[0],
            message="single candidate",
        )

    return IdentityResolution(
        status=IdentityStatus.AMBIGUOUS,
        candidates=unique,
        selected=None,
        message=f"{len(unique)} candidates — explicit selection required",
    )


def _fingerprint(t: TerminalInstance) -> str:
    parts = [
        str(t.platform.value if isinstance(t.platform, Platform) else t.platform),
        (t.executable_path or "").lower(),
        (t.data_path or "").lower(),
        (t.experts_path or "").lower(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
