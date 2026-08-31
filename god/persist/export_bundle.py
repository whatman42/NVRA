"""User-bound export/import of model and runtime state.

Does NOT store broker passwords, API secrets, or private signing keys.
Wrong-user load is BLOCKED.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from god.auth.identity import UserIdentity


class ExportError(Exception):
    pass


SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checksum(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass
class ExportBundle:
    schema_version: int
    owner_user_id: str
    owner_username: str
    owner_public_binding: str
    created_at: str
    model_metadata: Dict[str, Any] = field(default_factory=dict)
    calibration_state: Dict[str, Any] = field(default_factory=dict)
    checkpoint: Dict[str, Any] = field(default_factory=dict)
    configuration: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""

    def material_for_checksum(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "owner_user_id": self.owner_user_id,
            "owner_username": self.owner_username,
            "owner_public_binding": self.owner_public_binding,
            "created_at": self.created_at,
            "model_metadata": self.model_metadata,
            "calibration_state": self.calibration_state,
            "checkpoint": self.checkpoint,
            "configuration": self.configuration,
        }

    def seal(self) -> None:
        self.checksum = _checksum(self.material_for_checksum())

    def to_dict(self) -> Dict[str, Any]:
        d = self.material_for_checksum()
        d["checksum"] = self.checksum
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportBundle":
        try:
            bundle = cls(
                schema_version=int(data["schema_version"]),
                owner_user_id=str(data["owner_user_id"]),
                owner_username=str(data["owner_username"]),
                owner_public_binding=str(data["owner_public_binding"]),
                created_at=str(data["created_at"]),
                model_metadata=dict(data.get("model_metadata") or {}),
                calibration_state=dict(data.get("calibration_state") or {}),
                checkpoint=dict(data.get("checkpoint") or {}),
                configuration=dict(data.get("configuration") or {}),
                checksum=str(data.get("checksum") or ""),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ExportError(f"invalid bundle: {e}") from e
        return bundle

    def verify_integrity(self) -> None:
        expected = _checksum(self.material_for_checksum())
        if not self.checksum or self.checksum != expected:
            raise ExportError("checksum_mismatch")


def save_bundle(
    path: Path,
    identity: UserIdentity,
    *,
    model_metadata: Optional[Dict[str, Any]] = None,
    calibration_state: Optional[Dict[str, Any]] = None,
    checkpoint: Optional[Dict[str, Any]] = None,
    configuration: Optional[Dict[str, Any]] = None,
) -> ExportBundle:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = ExportBundle(
        schema_version=SCHEMA_VERSION,
        owner_user_id=identity.user_id,
        owner_username=identity.username,
        owner_public_binding=identity.public_binding,
        created_at=_utc_now(),
        model_metadata=dict(model_metadata or {}),
        calibration_state=dict(calibration_state or {}),
        checkpoint=dict(checkpoint or {}),
        configuration=dict(configuration or {}),
    )
    bundle.seal()
    path.write_text(json.dumps(bundle.to_dict(), indent=2), encoding="utf-8")
    return bundle


def load_bundle(path: Path) -> ExportBundle:
    path = Path(path)
    if not path.exists():
        raise ExportError("bundle_not_found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ExportError(f"unreadable_bundle: {e}") from e
    bundle = ExportBundle.from_dict(data)
    bundle.verify_integrity()
    return bundle


def verify_bundle_owner(bundle: ExportBundle, identity: UserIdentity) -> None:
    """BLOCK load when identity does not match owner binding."""
    if bundle.owner_user_id != identity.user_id:
        raise ExportError("wrong_user_blocked")
    if bundle.owner_public_binding != identity.public_binding:
        raise ExportError("binding_mismatch_blocked")
