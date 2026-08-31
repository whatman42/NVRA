"""Phase 6F — N.U.N.G. security models. AUTHORIZATION ≠ EXECUTION."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from god.research.provenance import content_hash


class AuthorizationState(str, Enum):
    DENIED = "DENIED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    CORRUPTED = "CORRUPTED"


class Capability(str, Enum):
    OBSERVE = "OBSERVE"
    RESEARCH = "RESEARCH"
    PAPER_TRADE = "PAPER_TRADE"
    SHADOW_TRADE = "SHADOW_TRADE"
    LIVE_EXECUTION = "LIVE_EXECUTION"
    ADMIN = "ADMIN"


class AuthEnvironment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PAPER = "paper"
    SHADOW = "shadow"
    PRODUCTION = "production"


SCHEMA_VERSION = "security-6f-v1"


@dataclass(frozen=True)
class AuthorizationGrant:
    authorization_id: str
    state: AuthorizationState
    subject: str
    issuer: str
    capability: Capability
    environment: AuthEnvironment
    issued_at: str
    expires_at: str
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    nonce: str = ""
    revision: int = 1
    decision_id: str = ""
    intent_id: str = ""
    risk_id: str = ""
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "state": self.state.value,
            "subject": self.subject,
            "issuer": self.issuer,
            "capability": self.capability.value,
            "environment": self.environment.value,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
            "revision": self.revision,
            "decision_id": self.decision_id,
            "intent_id": self.intent_id,
            "risk_id": self.risk_id,
            "correlation_id": self.correlation_id,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
        }


def canonical_auth_payload(
    subject: str,
    issuer: str,
    capability: Capability,
    environment: AuthEnvironment,
    issued_at: str,
    expires_at: str,
    nonce: str,
    revision: int,
    decision_id: str = "",
    intent_id: str = "",
    risk_id: str = "",
    correlation_id: str = "",
) -> dict[str, Any]:
    return {
        "subject": subject,
        "issuer": issuer,
        "capability": capability.value,
        "environment": environment.value,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "revision": revision,
        "decision_id": decision_id,
        "intent_id": intent_id,
        "risk_id": risk_id,
        "correlation_id": correlation_id,
        "schema_version": SCHEMA_VERSION,
    }


def make_authorization_id(payload: dict[str, Any]) -> str:
    return "auth-" + content_hash(payload)[:24]


def integrity_hash(payload: dict[str, Any]) -> str:
    return content_hash(payload)
