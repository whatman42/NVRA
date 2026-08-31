"""Phase 6G — provider-neutral fake provider. No broker SDK."""

from __future__ import annotations

from typing import Optional

from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import (
    ExecutionStatus,
    ProductionExecutionRequest,
    ProductionExecutionResult,
    ProviderHealth,
    ReconciliationState,
    make_execution_id,
)


class FakeProductionExecutionProvider:
    """Deterministic simulated provider for tests. Never contacts brokers."""

    def __init__(self, *, health_state: ProviderHealth = ProviderHealth.HEALTHY) -> None:
        self._health = health_state
        self._reject = False

    def set_health(self, state: ProviderHealth) -> None:
        self._health = state

    def set_reject(self, value: bool) -> None:
        self._reject = value

    def health(self) -> ProviderHealth:
        return self._health

    def submit(self, request: ProductionExecutionRequest) -> ProductionExecutionResult:
        now = utc_now()
        if self._health in (
            ProviderHealth.UNAVAILABLE,
            ProviderHealth.CORRUPTED,
            ProviderHealth.UNKNOWN,
        ):
            payload = {"request_id": request.request_id, "status": "UNAVAILABLE"}
            return ProductionExecutionResult(
                request_id=request.request_id,
                execution_id=make_execution_id(payload),
                status=ExecutionStatus.UNAVAILABLE,
                content_hash=content_hash(payload),
                provider_ref="fake",
                simulated=True,
                reconciliation=ReconciliationState.UNKNOWN,
                error_class="provider_unavailable",
                timestamp=now,
            )
        if self._reject:
            payload = {"request_id": request.request_id, "status": "REJECTED"}
            return ProductionExecutionResult(
                request_id=request.request_id,
                execution_id=make_execution_id(payload),
                status=ExecutionStatus.REJECTED,
                content_hash=content_hash(payload),
                provider_ref="fake",
                simulated=True,
                reconciliation=ReconciliationState.REJECTED,
                error_class="provider_rejected",
                timestamp=now,
            )
        # PAPER/SHADOW → simulated accept
        payload = {
            "request_id": request.request_id,
            "status": "SIMULATED",
            "mode": request.execution_mode.value,
        }
        return ProductionExecutionResult(
            request_id=request.request_id,
            execution_id=make_execution_id(payload),
            status=ExecutionStatus.SIMULATED,
            content_hash=content_hash(payload),
            provider_ref="fake",
            simulated=True,
            reconciliation=ReconciliationState.CONSISTENT,
            timestamp=now,
        )
