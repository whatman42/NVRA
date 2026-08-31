"""Final Gate 2 — provider-neutral broker interface + deterministic demo provider."""

from __future__ import annotations

from typing import Any, Optional, Protocol

from .models import AccountState, AccountType, ProviderHealth


class BrokerExecutionProvider(Protocol):
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def health(self) -> ProviderHealth: ...
    def account_state(self) -> AccountState: ...
    def open_positions(self) -> list[dict[str, Any]]: ...
    def orders(self) -> list[dict[str, Any]]: ...
    def submit(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def cancel(self, order_id: str) -> dict[str, Any]: ...
    def reconcile(self) -> dict[str, Any]: ...


class DemoBrokerProvider:
    """
    Deterministic fake demo provider for Gate 2 verification.
    NEVER contacts real brokers. NOT a live path.
    """

    def __init__(self) -> None:
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health(self) -> ProviderHealth:
        return ProviderHealth.HEALTHY if self._connected else ProviderHealth.UNAVAILABLE

    def account_state(self) -> AccountState:
        if not self._connected:
            return AccountState(account_type=AccountType.UNKNOWN, connected=False)
        return AccountState(
            broker="DEMO_PROVIDER",
            account_id="demo-001",
            server="demo-local",
            account_type=AccountType.DEMO,
            currency="USD",
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            free_margin=10000.0,
            leverage=1.0,
            open_positions=0,
            connected=True,
        )

    def open_positions(self) -> list[dict[str, Any]]:
        return []

    def orders(self) -> list[dict[str, Any]]:
        return []

    def submit(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self._connected:
            return {"status": "REJECTED", "reason": "not_connected"}
        # demo-only simulated accept — not live
        return {
            "status": "SIMULATED",
            "request_id": request.get("request_id", ""),
            "account_type": "DEMO",
            "live": False,
        }

    def cancel(self, order_id: str) -> dict[str, Any]:
        return {"status": "CANCELLED", "order_id": order_id, "live": False}

    def reconcile(self) -> dict[str, Any]:
        return {"status": "CONSISTENT", "live": False}
