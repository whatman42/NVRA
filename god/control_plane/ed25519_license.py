"""Ed25519 license signing — private key ADMIN only; clients verify with public key."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


@dataclass(frozen=True)
class LicenseKeyPair:
    private_key_pem: bytes
    public_key_pem: bytes

    @classmethod
    def generate(cls) -> "LicenseKeyPair":
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        return cls(
            private_key_pem=priv.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            public_key_pem=pub.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
        )


def canonical_payload(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_license_payload(private_pem: bytes, payload: Mapping[str, Any]) -> str:
    key = serialization.load_pem_private_key(private_pem, password=None)
    assert isinstance(key, Ed25519PrivateKey)
    return _b64(key.sign(canonical_payload(payload)))


def verify_license_payload(public_pem: bytes, payload: Mapping[str, Any], signature_b64: str) -> bool:
    try:
        key = serialization.load_pem_public_key(public_pem)
        assert isinstance(key, Ed25519PublicKey)
        key.verify(_b64d(signature_b64), canonical_payload(payload))
        return True
    except Exception:
        return False


def license_expired(payload: Mapping[str, Any], *, now: Optional[datetime] = None) -> bool:
    exp = payload.get("expires_at")
    if exp is None or exp == "":
        return False
    now = now or datetime.now(timezone.utc)
    try:
        exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        return now >= exp_dt
    except Exception:
        return True


def build_license_payload(
    *,
    username: str,
    license_id: str,
    issued_at: str,
    expires_at: Optional[str] = None,
    product: str = "NVRA",
    version: int = 1,
) -> dict[str, Any]:
    return {
        "product": product,
        "username": username,
        "license_id": license_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "version": version,
    }
