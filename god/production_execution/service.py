"""Phase 6G — ProductionExecutionService. Auth-gated, fail-closed, idempotent."""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now
from god.observability import EventType, ObservabilityService
from god.research.provenance import content_hash
from god.security import (
    AuthEnvironment,
    AuthorizationGrant,
    AuthorizationService,
    AuthorizationState,
    Capability,
    ExecutionBoundaryFirewall,
)

from .models import (
    ExecutionMode,
    ExecutionStatus,
    ProductionExecutionRequest,
    ProductionExecutionResult,
    ProviderHealth,
    ReconciliationState,
    make_request_id,
)
from .provider import FakeProductionExecutionProvider


class ProductionExecutionService:
    """
    Bridge: Intent + Auth → Provider.
    LIVE requires LIVE capability grant (never auto-issued in 6F/6G).
    """

    def __init__(
        self,
        provider: Optional[Any] = None,
        auth: Optional[AuthorizationService] = None,
        firewall: Optional[ExecutionBoundaryFirewall] = None,
        observability: Optional[ObservabilityService] = None,
        max_cache: int = 500,
    ) -> None:
        self.provider = provider or FakeProductionExecutionProvider()
        self.auth = auth or AuthorizationService()
        self.firewall = firewall or ExecutionBoundaryFirewall(self.auth)
        self.obs = observability or ObservabilityService()
        self._cache: dict[str, ProductionExecutionResult] = {}
        self._order: list[str] = []
        self.max_cache = max_cache

    def build_request(
        self,
        *,
        intent_id: str,
        decision_id: str,
        symbol: str,
        action: str,
        execution_mode: ExecutionMode,
        environment: str,
        authorization_id: str = "",
        correlation_id: str = "",
        risk_id: str = "",
        strategy_ref: str = "",
        observation_ts: str = "",
        created_at: Optional[str] = None,
    ) -> ProductionExecutionRequest:
        created = created_at or utc_now()
        payload = {
            "intent_id": intent_id,
            "decision_id": decision_id,
            "symbol": symbol,
            "action": action,
            "execution_mode": execution_mode.value,
            "environment": environment,
            "authorization_id": authorization_id,
            "correlation_id": correlation_id,
            "risk_id": risk_id,
            "strategy_ref": strategy_ref,
        }
        rid = make_request_id(payload)
        return ProductionExecutionRequest(
            request_id=rid,
            intent_id=intent_id,
            decision_id=decision_id,
            symbol=symbol,
            action=action,
            execution_mode=execution_mode,
            environment=environment,
            content_hash=content_hash(payload),
            strategy_ref=strategy_ref,
            observation_ts=observation_ts,
            created_at=created,
            authorization_id=authorization_id,
            correlation_id=correlation_id,
            risk_id=risk_id,
            provenance={"schema": "pex-6g"},
        )

    def submit(
        self,
        request: ProductionExecutionRequest,
        grant: Optional[AuthorizationGrant] = None,
        *,
        now_iso: Optional[str] = None,
    ) -> ProductionExecutionResult:
        now = now_iso or utc_now()
        self.obs.emit(EventType.CYCLE_STARTED, message="execution_request_created")

        # idempotency
        if request.request_id in self._cache:
            existing = self._cache[request.request_id]
            return existing

        # LIVE always fail-closed unless grant allows (6F never issues LIVE APPROVED)
        if request.execution_mode == ExecutionMode.LIVE:
            cap = Capability.LIVE_EXECUTION
            component = "live"
            env = AuthEnvironment.PRODUCTION
        elif request.execution_mode == ExecutionMode.SHADOW:
            cap = Capability.SHADOW_TRADE
            component = "shadow"
            env = AuthEnvironment.SHADOW
        else:
            cap = Capability.PAPER_TRADE
            component = "paper"
            env = AuthEnvironment.PAPER

        # map environment string loosely
        try:
            env = AuthEnvironment(request.environment.lower())
        except ValueError:
            pass

        if grant is None:
            result = self._reject(request, "missing_authorization", now)
            self.obs.emit(EventType.CYCLE_FAILED, message="execution_authorization_denied")
            return self._store(result)

        state = self.firewall.check(
            grant,
            component=component,
            capability=cap,
            environment=env,
            now_iso=now,
            decision_id=request.decision_id,
            intent_id=request.intent_id,
            risk_id=request.risk_id,
            correlation_id=request.correlation_id,
        )
        if state != AuthorizationState.APPROVED:
            result = self._reject(request, f"auth_{state.value.lower()}", now)
            self.obs.emit(EventType.CYCLE_FAILED, message="execution_authorization_denied")
            return self._store(result)

        if request.execution_mode == ExecutionMode.LIVE:
            # hard block even if somehow approved
            result = self._reject(request, "live_not_authorized_phase6g", now)
            return self._store(result)

        # provider health
        health = self.provider.health()
        if health in (
            ProviderHealth.UNAVAILABLE,
            ProviderHealth.CORRUPTED,
            ProviderHealth.UNKNOWN,
        ):
            result = self._reject(request, f"provider_{health.value.lower()}", now)
            result = ProductionExecutionResult(
                request_id=request.request_id,
                execution_id=result.execution_id,
                status=ExecutionStatus.UNAVAILABLE,
                content_hash=result.content_hash,
                simulated=True,
                reconciliation=ReconciliationState.UNKNOWN,
                error_class=result.error_class,
                timestamp=now,
            )
            return self._store(result)

        result = self.provider.submit(request)
        self.obs.emit(EventType.CYCLE_COMPLETED, message="execution_simulated")
        return self._store(result)

    def _reject(
        self, request: ProductionExecutionRequest, reason: str, now: str
    ) -> ProductionExecutionResult:
        payload = {"request_id": request.request_id, "status": "REJECTED", "reason": reason}
        return ProductionExecutionResult(
            request_id=request.request_id,
            execution_id="pex-" + content_hash(payload)[:24],
            status=ExecutionStatus.REJECTED,
            content_hash=content_hash(payload),
            simulated=True,
            reconciliation=ReconciliationState.REJECTED,
            error_class=reason,
            timestamp=now,
        )

    def _store(self, result: ProductionExecutionResult) -> ProductionExecutionResult:
        self._cache[result.request_id] = result
        if result.request_id not in self._order:
            self._order.append(result.request_id)
        while len(self._order) > self.max_cache:
            old = self._order.pop(0)
            self._cache.pop(old, None)
        return result
