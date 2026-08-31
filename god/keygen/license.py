"""License issuance and verification — binds to user_id, not filename."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .signing import SigningKeyPair


class LicenseError(Exception):
    pass


@dataclass(frozen=True)
class LicensePayload:
    user_id: str
    username: str
    public_binding: str
    issued_at: str
    schema_version: int = 1
    product: str = "NUNG"

    def canonical_bytes(self) -> bytes:
        data = {
            "schema_version": self.schema_version,
            "product": self.product,
            "user_id": self.user_id,
            "username": self.username,
            "public_binding": self.public_binding,
            "issued_at": self.issued_at,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "product": self.product,
            "user_id": self.user_id,
            "username": self.username,
            "public_binding": self.public_binding,
            "issued_at": self.issued_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LicensePayload":
        try:
            return cls(
                user_id=str(data["user_id"]),
                username=str(data["username"]),
                public_binding=str(data["public_binding"]),
                issued_at=str(data["issued_at"]),
                schema_version=int(data.get("schema_version", 1)),
                product=str(data.get("product", "NUNG")),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise LicenseError(f"invalid license payload: {e}") from e


def issue_license(payload: LicensePayload, keypair: SigningKeyPair) -> Dict[str, Any]:
    """Return signed license document. KeyGen only — not for NUNG.exe private key embed."""
    sig = keypair.sign(payload.canonical_bytes())
    return {
        "payload": payload.to_dict(),
        "signature": sig,
        "key_id": keypair.public_id,
    }


def verify_license(
    document: Dict[str, Any],
    keypair: SigningKeyPair,
    *,
    expected_user_id: Optional[str] = None,
) -> LicensePayload:
    if not isinstance(document, dict):
        raise LicenseError("license must be object")
    try:
        payload = LicensePayload.from_dict(document["payload"])
        signature = str(document["signature"])
    except (KeyError, TypeError, LicenseError) as e:
        raise LicenseError(f"malformed license: {e}") from e
    if not keypair.verify(payload.canonical_bytes(), signature):
        raise LicenseError("signature_invalid")
    if expected_user_id is not None and payload.user_id != expected_user_id:
        raise LicenseError("user_mismatch")
    return payload
