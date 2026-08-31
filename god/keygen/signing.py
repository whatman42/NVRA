"""Ephemeral signing helpers for tests/dev. Production private keys MUST NOT ship in NUNG.exe."""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SigningKeyPair:
    """HMAC-based key pair material for license binding (dev/test).

    Production should use hardware/offline signing. NUNG.exe only holds public verification material.
    """

    private_material: bytes
    public_id: str

    def sign(self, message: bytes) -> str:
        return hmac.new(self.private_material, message, hashlib.sha256).hexdigest()

    def verify(self, message: bytes, signature: str) -> bool:
        expected = self.sign(message)
        return hmac.compare_digest(expected, signature)


def generate_ephemeral_keypair() -> SigningKeyPair:
    material = os.urandom(32)
    public_id = hashlib.sha256(material).hexdigest()[:16]
    return SigningKeyPair(private_material=material, public_id=public_id)
