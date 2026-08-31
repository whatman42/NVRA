"""Final Gate 2 — live readiness gate. Fail-closed. DETECTION ≠ AUTHORIZATION."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from god.research.provenance import content_hash
from god.security import AuthorizationService, Capability

from .models import AccountState, AccountType, LiveReadinessState, ProviderHealth
from .provider import BrokerExecutionProvider, DemoBrokerProvider


@dataclass(frozen=True)
class ReadinessReport:
    state: LiveReadinessState
    account_type: AccountType
    live_execution_authorized: bool
    reasons: tuple[str, ...]
    content_hash: str
    account: Optional[dict[str, Any]] = None
    risk_gate: str = "RED"
    windows_build: str = "PENDING"
    broker_e2e: str = "PENDING"

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "account_type": self.account_type.value,
            "live_execution_authorized": self.live_execution_authorized,
            "reasons": list(self.reasons),
            "content_hash": self.content_hash,
            "account": self.account,
            "risk_gate": self.risk_gate,
            "windows_build": self.windows_build,
            "broker_e2e": self.broker_e2e,
        }


class LiveReadinessGate:
    """
    Advances readiness states fail-closed.
    LIVE execution remains unauthorized unless explicit grant (never auto in Gate 2).
    """

    def __init__(
        self,
        provider: Optional[BrokerExecutionProvider] = None,
        auth: Optional[AuthorizationService] = None,
        *,
        windows_build_available: bool = False,
    ) -> None:
        self.provider = provider or DemoBrokerProvider()
        self.auth = auth or AuthorizationService()
        self.windows_build_available = windows_build_available

    def evaluate(self, *, demo_verified: bool = False) -> ReadinessReport:
        reasons: list[str] = []
        connected = self.provider.connect()
        health = self.provider.health()
        account = self.provider.account_state()

        if not connected or health != ProviderHealth.HEALTHY:
            reasons.append("provider_unhealthy")
            return self._report(
                LiveReadinessState.NOT_READY,
                AccountType.UNKNOWN,
                reasons,
                account,
                risk="RED",
            )

        if account.account_type == AccountType.UNKNOWN:
            reasons.append("account_type_unknown")
            return self._report(
                LiveReadinessState.NOT_READY,
                AccountType.UNKNOWN,
                reasons,
                account,
                risk="RED",
            )

        if account.account_type == AccountType.DEMO:
            if demo_verified:
                state = LiveReadinessState.DEMO_VERIFIED
                risk = "GREEN"
            else:
                state = LiveReadinessState.DEMO_READY
                risk = "GREEN"
            # LIVE still blocked
            return self._report(
                state,
                AccountType.DEMO,
                ("demo_path_only", "live_execution_denied"),
                account,
                risk=risk,
                broker_e2e="SIMULATED" if demo_verified else "PENDING",
            )

        # LIVE account detected — detection ≠ authorization
        reasons.append("live_account_detected")
        reasons.append("live_execution_blocked_pending_authorization")
        if not self.windows_build_available:
            reasons.append("windows_build_pending")
        # Never auto-authorize LIVE
        return self._report(
            LiveReadinessState.LIVE_PREPARED
            if self.windows_build_available
            else LiveReadinessState.NOT_READY,
            AccountType.LIVE,
            tuple(reasons),
            account,
            risk="RED",
            broker_e2e="PENDING",
        )

    def controlled_demo_cycle(self) -> dict[str, Any]:
        """CONNECT → health → account → simulated submit → reconcile (demo only)."""
        self.provider.connect()
        acc = self.provider.account_state()
        if acc.account_type != AccountType.DEMO:
            return {"status": "REJECTED", "reason": "not_demo_account", "live": False}
        result = self.provider.submit(
            {"request_id": "demo-gate2-1", "symbol": "EURUSD", "action": "PAPER"}
        )
        recon = self.provider.reconcile()
        return {
            "status": "OK",
            "account_type": acc.account_type.value,
            "submit": result,
            "reconcile": recon,
            "live": False,
            "authorization": "NOT_REQUIRED_FOR_DEMO_SIM",
        }

    def emergency_halt(self) -> dict[str, Any]:
        self.provider.disconnect()
        return {"status": "HALTED", "live": False, "new_execution": "STOPPED"}

    def _report(
        self,
        state: LiveReadinessState,
        account_type: AccountType,
        reasons: tuple[str, ...] | list[str],
        account: AccountState,
        *,
        risk: str,
        broker_e2e: str = "PENDING",
    ) -> ReadinessReport:
        reasons_t = tuple(reasons)
        payload = {
            "state": state.value,
            "account_type": account_type.value,
            "reasons": list(reasons_t),
            "live_auth": False,
        }
        return ReadinessReport(
            state=state,
            account_type=account_type,
            live_execution_authorized=False,  # always false in Gate 2 implementation
            reasons=reasons_t,
            content_hash=content_hash(payload),
            account=account.to_dict(),
            risk_gate=risk,
            windows_build="AVAILABLE" if self.windows_build_available else "PENDING",
            broker_e2e=broker_e2e,
        )
