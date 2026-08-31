"""Phase 6F — N.U.N.G. capability & execution boundary firewall."""

from __future__ import annotations

from typing import Optional

from .authorization import AuthorizationService
from .models import (
    AuthEnvironment,
    AuthorizationGrant,
    AuthorizationState,
    Capability,
)


# Default capability matrix (component → allowed)
_COMPONENT_CAPS: dict[str, frozenset[Capability]] = {
    "research": frozenset({Capability.OBSERVE, Capability.RESEARCH}),
    "paper": frozenset({Capability.OBSERVE, Capability.PAPER_TRADE}),
    "shadow": frozenset({Capability.OBSERVE, Capability.SHADOW_TRADE}),
    "live": frozenset(),  # empty — LIVE blocked
    "admin": frozenset({Capability.OBSERVE, Capability.ADMIN}),
}


class ExecutionBoundaryFirewall:
    """
    Can this component perform this operation under this grant?
    LIVE_EXECUTION always blocked in Phase 6F.
    """

    def __init__(self, auth: Optional[AuthorizationService] = None) -> None:
        self.auth = auth or AuthorizationService()

    def component_allows(self, component: str, capability: Capability) -> bool:
        if capability == Capability.LIVE_EXECUTION:
            return False
        allowed = _COMPONENT_CAPS.get(component.lower(), frozenset())
        return capability in allowed

    def check(
        self,
        grant: Optional[AuthorizationGrant],
        *,
        component: str,
        capability: Capability,
        environment: AuthEnvironment,
        now_iso: Optional[str] = None,
        decision_id: str = "",
        intent_id: str = "",
        risk_id: str = "",
        correlation_id: str = "",
    ) -> AuthorizationState:
        if grant is None:
            return AuthorizationState.DENIED
        if not self.component_allows(component, capability):
            return AuthorizationState.DENIED
        if capability == Capability.LIVE_EXECUTION:
            return AuthorizationState.DENIED
        return self.auth.validate(
            grant,
            now_iso=now_iso,
            required_capability=capability,
            required_environment=environment,
            expected_decision_id=decision_id,
            expected_intent_id=intent_id,
            expected_risk_id=risk_id,
            expected_correlation_id=correlation_id,
        )

    def allow_execution(
        self,
        grant: Optional[AuthorizationGrant],
        **kwargs,
    ) -> bool:
        """True only if validation returns APPROVED and capability is not LIVE."""
        state = self.check(grant, **kwargs)
        return state == AuthorizationState.APPROVED
