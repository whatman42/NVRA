"""NullExecutionProvider — no transactions, pure dry-run / unit-test target."""

from __future__ import annotations

from typing import Optional, Sequence, Dict, Any
import threading

from god.agent.models import (
    AccountState,
    MarketState,
    ExecutionRequest,
    ExecutionResult,
    ActionType,
    new_id,
)
from god.memory.database import utc_now


class NullExecutionProvider:
    """Does nothing. Always succeeds for NO_ACTION / OBSERVE_ONLY;
    returns success=False for OPEN/CLOSE/MODIFY so callers can test
    the failure path without side effects.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._seen: Dict[str, ExecutionResult] = {}
        self._account = AccountState(balance=10_000.0, equity=10_000.0, free_margin=10_000.0)

    @property
    def name(self) -> str:
        return "null"

    def get_account_state(self) -> AccountState:
        return self._account

    def get_positions(self) -> Sequence[dict]:
        return []

    def get_orders(self) -> Sequence[dict]:
        return []

    def get_market_state(self, symbol: Optional[str] = None) -> MarketState:
        return MarketState(symbol=symbol, bid=None, ask=None, last=None, timestamp=utc_now())

    def submit(self, request: ExecutionRequest) -> ExecutionResult:
        with self._lock:
            if request.request_id in self._seen:
                original = self._seen[request.request_id]
                return ExecutionResult(
                    request_id=original.request_id,
                    decision_id=original.decision_id,
                    success=original.success,
                    executed_action=original.executed_action,
                    timestamp=utc_now(),
                    order_id=original.order_id,
                    position_id=original.position_id,
                    fill_price=original.fill_price,
                    volume=original.volume,
                    fees=original.fees,
                    slippage=original.slippage,
                    message=original.message,
                    is_duplicate=True,
                    metadata=dict(original.metadata),
                )

            if request.action in (ActionType.NO_ACTION, ActionType.OBSERVE_ONLY):
                result = ExecutionResult.create(
                    request_id=request.request_id,
                    decision_id=request.decision_id,
                    success=True,
                    executed_action=request.action,
                    message="null provider: no-op",
                )
            else:
                result = ExecutionResult.create(
                    request_id=request.request_id,
                    decision_id=request.decision_id,
                    success=False,
                    executed_action=ActionType.NO_ACTION,
                    message=f"null provider refuses action {request.action.value}",
                )
            self._seen[request.request_id] = result
            return result

    def cancel(self, order_id: str) -> ExecutionResult:
        return ExecutionResult.create(
            request_id=new_id(),
            decision_id="",
            success=False,
            executed_action=ActionType.NO_ACTION,
            message="null provider: cancel not supported",
        )

    def reconcile(self) -> dict:
        return {
            "provider": self.name,
            "open_positions": 0,
            "pending_orders": 0,
            "seen_requests": len(self._seen),
        }
