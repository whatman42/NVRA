"""VirtualExecutionProvider — in-memory simulator for closed-loop testing.

No broker connection. Supports OPEN / CLOSE / MODIFY with simple fills.
Idempotent on request_id.
"""

from __future__ import annotations

from typing import Optional, Sequence, Dict, Any, List
import threading
import copy

from god.agent.models import (
    AccountState,
    MarketState,
    ExecutionRequest,
    ExecutionResult,
    ActionType,
    new_id,
)
from god.memory.database import utc_now


class VirtualExecutionProvider:
    """Simulates account, positions and fills.

    Design choices (deliberately minimal, no strategy):
    - Fixed bid/ask spread for fills
    - Instant fill at mid ± half-spread
    - Simple fee model
    - request_id idempotency map
    """

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        default_symbol: str = "EURUSD",
        bid: float = 1.10000,
        ask: float = 1.10020,
        fee_per_lot: float = 0.0,
    ) -> None:
        self._lock = threading.RLock()
        self._balance = float(initial_balance)
        self._equity = float(initial_balance)
        self._default_symbol = default_symbol
        self._bid = float(bid)
        self._ask = float(ask)
        self._fee_per_lot = float(fee_per_lot)
        self._positions: Dict[str, dict] = {}
        self._orders: Dict[str, dict] = {}
        self._seen: Dict[str, ExecutionResult] = {}
        self._trade_log: List[dict] = []

    @property
    def name(self) -> str:
        return "virtual"

    def get_account_state(self) -> AccountState:
        with self._lock:
            self._recalc_equity()
            return AccountState(
                balance=self._balance,
                equity=self._equity,
                margin=0.0,
                free_margin=self._equity,
                currency="USD",
                leverage=100.0,
            )

    def get_positions(self) -> Sequence[dict]:
        with self._lock:
            return [copy.deepcopy(p) for p in self._positions.values() if p.get("status") == "OPEN"]

    def get_orders(self) -> Sequence[dict]:
        with self._lock:
            return [copy.deepcopy(o) for o in self._orders.values()]

    def get_market_state(self, symbol: Optional[str] = None) -> MarketState:
        sym = symbol or self._default_symbol
        return MarketState(
            symbol=sym,
            bid=self._bid,
            ask=self._ask,
            last=(self._bid + self._ask) / 2.0,
            timestamp=utc_now(),
        )

    def set_quotes(self, bid: float, ask: float) -> None:
        """Test helper: move the simulated market."""
        with self._lock:
            self._bid = float(bid)
            self._ask = float(ask)
            self._recalc_equity()

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
                    message="virtual: no-op",
                )
            elif request.action == ActionType.OPEN:
                result = self._open(request)
            elif request.action == ActionType.CLOSE:
                result = self._close(request)
            elif request.action == ActionType.MODIFY:
                result = self._modify(request)
            else:
                result = ExecutionResult.create(
                    request_id=request.request_id,
                    decision_id=request.decision_id,
                    success=False,
                    executed_action=ActionType.NO_ACTION,
                    message=f"virtual: unknown action {request.action}",
                )

            self._seen[request.request_id] = result
            return result

    def cancel(self, order_id: str) -> ExecutionResult:
        with self._lock:
            if order_id in self._orders:
                del self._orders[order_id]
                return ExecutionResult.create(
                    request_id=new_id(),
                    decision_id="",
                    success=True,
                    executed_action=ActionType.NO_ACTION,
                    message=f"virtual: cancelled {order_id}",
                    order_id=order_id,
                )
            return ExecutionResult.create(
                request_id=new_id(),
                decision_id="",
                success=False,
                executed_action=ActionType.NO_ACTION,
                message=f"virtual: order {order_id} not found",
            )

    def reconcile(self) -> dict:
        with self._lock:
            self._recalc_equity()
            return {
                "provider": self.name,
                "balance": self._balance,
                "equity": self._equity,
                "open_positions": len([p for p in self._positions.values() if p.get("status") == "OPEN"]),
                "pending_orders": len(self._orders),
                "seen_requests": len(self._seen),
                "trade_log_count": len(self._trade_log),
            }

    # ── internal helpers ─────────────────────────────────────────────────

    def _recalc_equity(self) -> None:
        unrealized = 0.0
        for p in self._positions.values():
            if p.get("status") != "OPEN":
                continue
            entry = p["entry_price"]
            vol = p["volume"]
            side = p["side"]
            mark = self._bid if side == "BUY" else self._ask
            if side == "BUY":
                unrealized += (mark - entry) * vol * 100_000  # simplistic pip value
            else:
                unrealized += (entry - mark) * vol * 100_000
            p["current_price"] = mark
            p["unrealized_pnl"] = (mark - entry) * vol * 100_000 if side == "BUY" else (entry - mark) * vol * 100_000
        self._equity = self._balance + unrealized

    def _open(self, request: ExecutionRequest) -> ExecutionResult:
        symbol = request.symbol or self._default_symbol
        volume = float(request.volume or 0.01)
        side = (request.side or "BUY").upper()
        if side not in ("BUY", "SELL"):
            return ExecutionResult.create(
                request_id=request.request_id,
                decision_id=request.decision_id,
                success=False,
                executed_action=ActionType.NO_ACTION,
                message=f"virtual: invalid side {side}",
            )
        if volume <= 0:
            return ExecutionResult.create(
                request_id=request.request_id,
                decision_id=request.decision_id,
                success=False,
                executed_action=ActionType.NO_ACTION,
                message="virtual: volume must be > 0",
            )

        fill = self._ask if side == "BUY" else self._bid
        fees = self._fee_per_lot * volume
        pos_id = new_id()
        order_id = new_id()
        now = utc_now()

        pos = {
            "position_id": pos_id,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "entry_price": fill,
            "current_price": fill,
            "sl": request.sl,
            "tp": request.tp,
            "unrealized_pnl": 0.0,
            "status": "OPEN",
            "opened_at": now,
            "is_virtual": True,
            "broker_ticket": order_id,
        }
        self._positions[pos_id] = pos
        self._balance -= fees
        self._recalc_equity()

        self._trade_log.append({"action": "OPEN", "position_id": pos_id, "request_id": request.request_id})

        return ExecutionResult.create(
            request_id=request.request_id,
            decision_id=request.decision_id,
            success=True,
            executed_action=ActionType.OPEN,
            order_id=order_id,
            position_id=pos_id,
            fill_price=fill,
            volume=volume,
            fees=fees,
            slippage=0.0,
            message="virtual: opened",
        )

    def _close(self, request: ExecutionRequest) -> ExecutionResult:
        pos_id = request.position_id
        if not pos_id or pos_id not in self._positions:
            return ExecutionResult.create(
                request_id=request.request_id,
                decision_id=request.decision_id,
                success=False,
                executed_action=ActionType.NO_ACTION,
                message=f"virtual: position {pos_id} not found",
            )
        pos = self._positions[pos_id]
        if pos.get("status") != "OPEN":
            return ExecutionResult.create(
                request_id=request.request_id,
                decision_id=request.decision_id,
                success=False,
                executed_action=ActionType.NO_ACTION,
                message=f"virtual: position {pos_id} already closed",
            )

        side = pos["side"]
        fill = self._bid if side == "BUY" else self._ask
        entry = pos["entry_price"]
        volume = pos["volume"]
        if side == "BUY":
            pnl = (fill - entry) * volume * 100_000
        else:
            pnl = (entry - fill) * volume * 100_000
        fees = self._fee_per_lot * volume
        self._balance += pnl - fees
        pos["status"] = "CLOSED"
        pos["exit_price"] = fill
        pos["pnl"] = pnl
        pos["closed_at"] = utc_now()
        self._recalc_equity()

        self._trade_log.append({"action": "CLOSE", "position_id": pos_id, "request_id": request.request_id, "pnl": pnl})

        return ExecutionResult.create(
            request_id=request.request_id,
            decision_id=request.decision_id,
            success=True,
            executed_action=ActionType.CLOSE,
            position_id=pos_id,
            fill_price=fill,
            volume=volume,
            fees=fees,
            message="virtual: closed",
            metadata={"pnl": pnl},
        )

    def _modify(self, request: ExecutionRequest) -> ExecutionResult:
        pos_id = request.position_id
        if not pos_id or pos_id not in self._positions:
            return ExecutionResult.create(
                request_id=request.request_id,
                decision_id=request.decision_id,
                success=False,
                executed_action=ActionType.NO_ACTION,
                message=f"virtual: position {pos_id} not found",
            )
        pos = self._positions[pos_id]
        if pos.get("status") != "OPEN":
            return ExecutionResult.create(
                request_id=request.request_id,
                decision_id=request.decision_id,
                success=False,
                executed_action=ActionType.NO_ACTION,
                message=f"virtual: position {pos_id} not open",
            )
        if request.sl is not None:
            pos["sl"] = request.sl
        if request.tp is not None:
            pos["tp"] = request.tp
        return ExecutionResult.create(
            request_id=request.request_id,
            decision_id=request.decision_id,
            success=True,
            executed_action=ActionType.MODIFY,
            position_id=pos_id,
            message="virtual: modified",
        )
