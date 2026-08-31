"""ExecutionProvider contract — environment-agnostic.

Implementations: Null (dry-run), Virtual (simulator).
Future: MT4 / MT5 bridges via IPC (Phase 4).
No trading intelligence lives here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional, Any, Sequence

from god.agent.models import (
    AccountState,
    MarketState,
    ExecutionRequest,
    ExecutionResult,
    ActionType,
)


@runtime_checkable
class ExecutionProvider(Protocol):
    """Broker / simulator abstraction.

    Methods are intentionally minimal and environment-agnostic so that
    Null, Virtual, and future MT* bridges share the same contract.
    """

    @property
    def name(self) -> str:
        """Provider identifier, e.g. 'null', 'virtual'."""
        ...

    def get_account_state(self) -> AccountState:
        ...

    def get_positions(self) -> Sequence[dict]:
        """Return list of open position dicts (provider-specific shape ok)."""
        ...

    def get_orders(self) -> Sequence[dict]:
        ...

    def get_market_state(self, symbol: Optional[str] = None) -> MarketState:
        ...

    def submit(self, request: ExecutionRequest) -> ExecutionResult:
        """Submit an execution request.

        Must be idempotent on request.request_id:
        - first call performs the action
        - subsequent calls with same request_id return the original result
          with is_duplicate=True and do not create a second transaction.
        """
        ...

    def cancel(self, order_id: str) -> ExecutionResult:
        ...

    def reconcile(self) -> dict:
        """Reconcile internal state with reality (or simulated reality).

        Called during recovery after crash.
        Returns a summary dict (e.g. open positions, pending requests).
        """
        ...
