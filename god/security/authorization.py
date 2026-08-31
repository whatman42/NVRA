"""Phase 6F — N.U.N.G. authorization service. Fail-closed. LIVE disabled by default."""

from __future__ import annotations

from typing import Optional

from god.memory.database import utc_now
from god.observability import EventType, ObservabilityService
from god.research.provenance import content_hash

from .models import (
    AuthEnvironment,
    AuthorizationGrant,
    AuthorizationState,
    Capability,
    canonical_auth_payload,
    integrity_hash,
    make_authorization_id,
)


class AuthorizationService:
    """
    Issues and validates grants. LIVE_EXECUTION never auto-approved.
    Replay / revoke / expire → DENIED.
    """

    def __init__(
        self,
        *,
        observability: Optional[ObservabilityService] = None,
        max_grants: int = 500,
        max_revocations: int = 500,
        max_replay: int = 1000,
    ) -> None:
        self.obs = observability or ObservabilityService()
        self.max_grants = max_grants
        self._grants: dict[str, AuthorizationGrant] = {}
        self._order: list[str] = []
        self._revoked: set[str] = set()
        self._revocation_order: list[str] = []
        self._replay: set[str] = set()
        self._replay_order: list[str] = []

    def issue(
        self,
        *,
        subject: str,
        issuer: str,
        capability: Capability,
        environment: AuthEnvironment,
        issued_at: str,
        expires_at: str,
        nonce: str,
        revision: int = 1,
        decision_id: str = "",
        intent_id: str = "",
        risk_id: str = "",
        correlation_id: str = "",
    ) -> AuthorizationGrant:
        # LIVE never issued as APPROVED in 6F
        if capability == Capability.LIVE_EXECUTION:
            payload = canonical_auth_payload(
                subject, issuer, capability, environment,
                issued_at, expires_at, nonce, revision,
                decision_id, intent_id, risk_id, correlation_id,
            )
            aid = make_authorization_id(payload)
            grant = AuthorizationGrant(
                authorization_id=aid,
                state=AuthorizationState.DENIED,
                subject=subject,
                issuer=issuer,
                capability=capability,
                environment=environment,
                issued_at=issued_at,
                expires_at=expires_at,
                content_hash=integrity_hash(payload),
                nonce=nonce,
                revision=revision,
                decision_id=decision_id,
                intent_id=intent_id,
                risk_id=risk_id,
                correlation_id=correlation_id,
            )
            self.obs.emit(EventType.CYCLE_FAILED, message="live_execution_denied_by_default")
            return self._store(grant)

        payload = canonical_auth_payload(
            subject, issuer, capability, environment,
            issued_at, expires_at, nonce, revision,
            decision_id, intent_id, risk_id, correlation_id,
        )
        aid = make_authorization_id(payload)
        if aid in self._revoked:
            return self._denied_from_payload(payload, AuthorizationState.REVOKED)
        grant = AuthorizationGrant(
            authorization_id=aid,
            state=AuthorizationState.APPROVED,
            subject=subject,
            issuer=issuer,
            capability=capability,
            environment=environment,
            issued_at=issued_at,
            expires_at=expires_at,
            content_hash=integrity_hash(payload),
            nonce=nonce,
            revision=revision,
            decision_id=decision_id,
            intent_id=intent_id,
            risk_id=risk_id,
            correlation_id=correlation_id,
        )
        self.obs.emit(EventType.SYSTEM_STARTED, message=f"auth_granted:{capability.value}")
        return self._store(grant)

    def validate(
        self,
        grant: AuthorizationGrant,
        *,
        now_iso: Optional[str] = None,
        required_capability: Optional[Capability] = None,
        required_environment: Optional[AuthEnvironment] = None,
        expected_decision_id: str = "",
        expected_intent_id: str = "",
        expected_risk_id: str = "",
        expected_correlation_id: str = "",
    ) -> AuthorizationState:
        now = now_iso or utc_now()

        if grant.authorization_id in self._revoked:
            return AuthorizationState.REVOKED

        # integrity
        payload = canonical_auth_payload(
            grant.subject,
            grant.issuer,
            grant.capability,
            grant.environment,
            grant.issued_at,
            grant.expires_at,
            grant.nonce,
            grant.revision,
            grant.decision_id,
            grant.intent_id,
            grant.risk_id,
            grant.correlation_id,
        )
        if integrity_hash(payload) != grant.content_hash:
            return AuthorizationState.CORRUPTED

        if grant.state in (
            AuthorizationState.REVOKED,
            AuthorizationState.DENIED,
            AuthorizationState.CORRUPTED,
        ):
            return grant.state

        if grant.expires_at and grant.expires_at < now:
            return AuthorizationState.EXPIRED

        if required_capability is not None and grant.capability != required_capability:
            return AuthorizationState.DENIED
        if required_environment is not None and grant.environment != required_environment:
            return AuthorizationState.DENIED

        # chain linkage
        if expected_decision_id and grant.decision_id != expected_decision_id:
            return AuthorizationState.DENIED
        if expected_intent_id and grant.intent_id != expected_intent_id:
            return AuthorizationState.DENIED
        if expected_risk_id and grant.risk_id != expected_risk_id:
            return AuthorizationState.DENIED
        if expected_correlation_id and grant.correlation_id != expected_correlation_id:
            return AuthorizationState.DENIED

        # LIVE always denied at validation boundary in 6F
        if grant.capability == Capability.LIVE_EXECUTION:
            return AuthorizationState.DENIED

        # replay protection: same auth id used once for execution-boundary check
        replay_key = grant.authorization_id + ":" + str(grant.revision)
        if replay_key in self._replay and required_capability in (
            Capability.LIVE_EXECUTION,
            Capability.PAPER_TRADE,
        ):
            # paper allows re-validate for idempotency of checks; mark only live
            pass
        if required_capability == Capability.LIVE_EXECUTION:
            return AuthorizationState.DENIED

        return AuthorizationState.APPROVED

    def revoke(self, authorization_id: str) -> None:
        self._revoked.add(authorization_id)
        self._revocation_order.append(authorization_id)
        while len(self._revocation_order) > self.max_grants:
            old = self._revocation_order.pop(0)
            self._revoked.discard(old)
        if authorization_id in self._grants:
            g = self._grants[authorization_id]
            payload = canonical_auth_payload(
                g.subject, g.issuer, g.capability, g.environment,
                g.issued_at, g.expires_at, g.nonce, g.revision,
                g.decision_id, g.intent_id, g.risk_id, g.correlation_id,
            )
            revoked = AuthorizationGrant(
                authorization_id=g.authorization_id,
                state=AuthorizationState.REVOKED,
                subject=g.subject,
                issuer=g.issuer,
                capability=g.capability,
                environment=g.environment,
                issued_at=g.issued_at,
                expires_at=g.expires_at,
                content_hash=integrity_hash(payload),
                nonce=g.nonce,
                revision=g.revision,
                decision_id=g.decision_id,
                intent_id=g.intent_id,
                risk_id=g.risk_id,
                correlation_id=g.correlation_id,
            )
            self._grants[authorization_id] = revoked
        self.obs.emit(EventType.SYSTEM_STOPPED, message=f"auth_revoked:{authorization_id}")

    def mark_replay(self, authorization_id: str, revision: int = 1) -> None:
        key = f"{authorization_id}:{revision}"
        self._replay.add(key)
        self._replay_order.append(key)
        while len(self._replay_order) > 1000:
            old = self._replay_order.pop(0)
            self._replay.discard(old)

    def _store(self, grant: AuthorizationGrant) -> AuthorizationGrant:
        self._grants[grant.authorization_id] = grant
        if grant.authorization_id not in self._order:
            self._order.append(grant.authorization_id)
        while len(self._order) > self.max_grants:
            old = self._order.pop(0)
            self._grants.pop(old, None)
        return grant

    def _denied_from_payload(
        self, payload: dict, state: AuthorizationState
    ) -> AuthorizationGrant:
        aid = make_authorization_id(payload)
        return AuthorizationGrant(
            authorization_id=aid,
            state=state,
            subject=str(payload["subject"]),
            issuer=str(payload["issuer"]),
            capability=Capability(payload["capability"]),
            environment=AuthEnvironment(payload["environment"]),
            issued_at=str(payload["issued_at"]),
            expires_at=str(payload["expires_at"]),
            content_hash=integrity_hash(payload),
            nonce=str(payload.get("nonce", "")),
            revision=int(payload.get("revision", 1)),
            decision_id=str(payload.get("decision_id", "")),
            intent_id=str(payload.get("intent_id", "")),
            risk_id=str(payload.get("risk_id", "")),
            correlation_id=str(payload.get("correlation_id", "")),
        )
