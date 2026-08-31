"""ExecutionEngine — sole path from approved RiskDecision to exchange.

Never bypasses RiskEngine. PAPER mode never calls real create_order.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from crypto.exchanges.base import ExchangeAdapter
from crypto.exchanges.errors import ExchangeError, TradingDisabledError
from crypto.execution.models import (
    ExecutionMode,
    ExecutionRecord,
    Fill,
    make_client_order_id,
    now_ms,
    record_from_decision,
)
from crypto.execution.paper import PaperBroker
from crypto.execution.states import (
    OrderState,
    TransitionError,
    is_terminal,
    transition,
)
from crypto.execution.store import ExecutionStore
from crypto.market.quality import DataQualityReport
from crypto.portfolio.models import PortfolioSnapshot
from crypto.risk.engine import RiskEngine
from crypto.risk.models import (
    MarketConstraints,
    RiskDecision,
    RiskVerdict,
    SafetyMode,
    Side,
)

logger = logging.getLogger(__name__)


def _as_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class ExecutionError(Exception):
    """Execution-layer failure (not an exchange transport error)."""


class ExecutionEngine:
    """Submit only after RiskDecision.APPROVED + final risk re-check."""

    def __init__(
        self,
        adapter: ExchangeAdapter,
        risk_engine: RiskEngine,
        store: ExecutionStore,
        *,
        mode: ExecutionMode = ExecutionMode.PAPER,
        paper_broker: PaperBroker | None = None,
    ) -> None:
        self._adapter = adapter
        self._risk = risk_engine
        self._store = store
        self._mode = mode
        self._paper = paper_broker or PaperBroker()
        # Ensure adapter trading is off unless we explicitly enable for LIVE submit
        self._adapter.enable_trading(False)

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    def set_mode(self, mode: ExecutionMode) -> None:
        """LIVE must be explicit. Prefer constructing with PAPER by default."""
        if mode is ExecutionMode.LIVE:
            logger.warning("execution mode set to LIVE")
        self._mode = mode
        self._adapter.enable_trading(False)

    @contextmanager
    def _live_trading_gate(self) -> Iterator[None]:
        """Temporarily enable adapter trading for a single LIVE submit/cancel."""
        if self._mode is not ExecutionMode.LIVE:
            yield
            return
        try:
            self._adapter.enable_trading(True)
            yield
        finally:
            self._adapter.enable_trading(False)

    def submit(
        self,
        decision: RiskDecision,
        portfolio: PortfolioSnapshot,
        *,
        order_type: str = "limit",
        intent_key: str,
        market_quality: DataQualityReport | None = None,
        constraints: MarketConstraints | None = None,
        entry_price: float | None = None,
        exchange_available: bool = True,
    ) -> ExecutionRecord:
        """Execute an approved risk decision (or reject without submitting)."""
        if decision.verdict is not RiskVerdict.APPROVED or not decision.executable:
            raise ExecutionError(
                f"cannot execute non-approved decision: {decision.verdict.name} "
                f"({decision.reason.name})"
            )
        if decision.proposal is None:
            raise ExecutionError("decision has no proposal")

        # Idempotency: same intent must not create a second order
        client_oid = make_client_order_id(
            decision.proposal.exchange_id,
            decision.proposal.account_id,
            decision.proposal.symbol,
            decision.proposal.side,
            decision.allowed_quantity,
            decision.proposal.requested_price,
            intent_key,
        )
        existing = self._store.get_by_client_order_id(client_oid)
        if existing is not None and not is_terminal(existing.state):
            self._audit(existing, "idempotent_hit", "returning existing active execution")
            return existing
        if existing is not None and existing.state is OrderState.FILLED:
            self._audit(existing, "idempotent_hit", "already filled")
            return existing

        rec = record_from_decision(
            decision, order_type=order_type, mode=self._mode, intent_key=intent_key
        )
        # Force client_order_id to the deterministic one
        rec.client_order_id = client_oid
        self._set_state(rec, OrderState.RISK_APPROVED)
        self._store.save(rec)
        self._audit(rec, "risk_approved", decision.message)

        # Emergency stop / safety
        if self._risk.safety_mode is SafetyMode.EMERGENCY_STOP:
            return self._reject_local(rec, "EMERGENCY_STOP")

        # FINAL pre-submission risk check
        final = self._risk.evaluate(
            decision.proposal,
            portfolio,
            market_quality=market_quality,
            constraints=constraints,
            entry_price=entry_price or decision.proposal.requested_price,
            exchange_available=exchange_available,
        )
        self._audit(
            rec,
            "final_risk_check",
            f"{final.verdict.name}:{final.reason.name}:{final.message}",
        )
        if final.verdict is not RiskVerdict.APPROVED or not final.executable:
            return self._reject_local(
                rec, f"final risk failed: {final.reason.name} {final.message}"
            )

        # Use final allowed size (may be tighter)
        if final.allowed_quantity < rec.allowed_quantity:
            rec.allowed_quantity = final.allowed_quantity
            rec.allowed_notional = final.allowed_notional
            rec.remaining_quantity = final.allowed_quantity

        # Precision: never round up past risk
        if constraints and constraints.amount_precision is not None:
            factor = 10**constraints.amount_precision
            floored = int(rec.allowed_quantity * factor) / factor
            if floored <= 0:
                return self._reject_local(rec, "quantity floors to zero")
            if floored < rec.allowed_quantity:
                rec.allowed_quantity = floored
                rec.allowed_notional = floored * (
                    entry_price or decision.proposal.requested_price or 0
                )
                rec.remaining_quantity = floored

        return self._submit_to_venue(rec)

    def _submit_to_venue(self, rec: ExecutionRecord) -> ExecutionRecord:
        self._set_state(rec, OrderState.SUBMITTING)
        self._store.save(rec)
        self._audit(rec, "submitting", f"mode={self._mode.name}")

        side = "buy" if rec.side is Side.BUY else "sell"
        try:
            if self._mode is ExecutionMode.PAPER:
                raw = self._paper.create_order(
                    rec.symbol,
                    side,
                    rec.order_type,
                    rec.allowed_quantity,
                    rec.requested_price,
                    client_order_id=rec.client_order_id,
                )
            else:
                with self._live_trading_gate():
                    params: dict[str, object] = {
                        "clientOrderId": rec.client_order_id,
                    }
                    raw = self._adapter.create_order(
                        rec.symbol,
                        side,
                        rec.order_type,
                        rec.allowed_quantity,
                        rec.requested_price,
                        params,
                    )
        except TradingDisabledError as exc:
            self._set_state(rec, OrderState.FAILED)
            rec.last_error = str(exc)
            self._store.save(rec)
            self._audit(rec, "trading_disabled", str(exc))
            raise
        except ExchangeError as exc:
            # Ambiguous network after send → UNKNOWN, not FAILED-retry
            msg = str(exc)
            if "Network" in type(exc).__name__ or "timeout" in msg.lower():
                self._set_state(rec, OrderState.UNKNOWN)
                rec.last_error = msg
                self._store.save(rec)
                self._audit(rec, "unknown_after_submit", msg)
                return rec
            self._set_state(rec, OrderState.FAILED)
            rec.last_error = msg
            self._store.save(rec)
            self._audit(rec, "submit_failed", msg)
            return rec
        except Exception as exc:  # noqa: BLE001
            self._set_state(rec, OrderState.UNKNOWN)
            rec.last_error = str(exc)
            self._store.save(rec)
            self._audit(rec, "unknown_after_submit", type(exc).__name__)
            return rec

        return self._apply_exchange_response(rec, raw)

    def _apply_exchange_response(
        self, rec: ExecutionRecord, raw: dict[str, object]
    ) -> ExecutionRecord:
        rec.exchange_order_id = str(raw.get("id") or "") or None
        status = str(raw.get("status") or "").lower()
        filled = _as_float(raw.get("filled"), 0.0)
        remaining = _as_float(raw.get("remaining"), max(0.0, rec.allowed_quantity - filled))
        avg = raw.get("average") or raw.get("price")
        fee_raw = raw.get("fee")
        fee_info: dict[str, object] = fee_raw if isinstance(fee_raw, dict) else {}

        if filled > 0:
            fee_cost = fee_info.get("cost")
            fee_cur = fee_info.get("currency")
            fill = Fill(
                fill_id=f"{rec.exchange_order_id or rec.execution_id}-f0",
                quantity=filled,
                price=_as_float(avg, rec.requested_price or 0.0),
                fee_amount=_as_float(fee_cost, 0.0) if fee_cost is not None else None,
                fee_currency=str(fee_cur) if fee_cur is not None else None,
                timestamp_ms=int(_as_float(raw.get("timestamp"), float(now_ms()))),
            )
            rec.fills.append(fill)
            rec.recompute_from_fills()
        else:
            rec.remaining_quantity = remaining

        if status in ("closed", "filled") or (rec.filled_quantity >= rec.allowed_quantity - 1e-12):
            self._set_state(rec, OrderState.FILLED)
            rec.remaining_quantity = 0.0
        elif filled > 0:
            self._set_state(rec, OrderState.PARTIALLY_FILLED)
        elif status in ("open", "new", "live"):
            self._set_state(rec, OrderState.OPEN)
        elif status in ("canceled", "cancelled", "expired"):
            self._set_state(rec, OrderState.CANCELLED)
        elif status in ("rejected",):
            self._set_state(rec, OrderState.REJECTED)
        else:
            self._set_state(rec, OrderState.SUBMITTED)

        rec.updated_at_ms = now_ms()
        self._store.save(rec)
        self._audit(rec, "exchange_response", f"status={status} filled={filled}")
        return rec

    def cancel(self, execution_id: str) -> ExecutionRecord:
        rec = self._store.get(execution_id)
        if rec is None:
            raise ExecutionError(f"unknown execution_id={execution_id}")
        if is_terminal(rec.state):
            return rec
        self._set_state(rec, OrderState.CANCEL_PENDING)
        self._store.save(rec)
        self._audit(rec, "cancel_requested", "")

        try:
            if self._mode is ExecutionMode.PAPER:
                oid = rec.exchange_order_id or ""
                raw = self._paper.cancel_order(oid, rec.symbol)
            else:
                if not rec.exchange_order_id:
                    self._set_state(rec, OrderState.UNKNOWN)
                    rec.last_error = "no exchange_order_id for cancel"
                    self._store.save(rec)
                    return rec
                with self._live_trading_gate():
                    raw = self._adapter.cancel_order(rec.exchange_order_id, rec.symbol)
        except Exception as exc:  # noqa: BLE001
            self._set_state(rec, OrderState.UNKNOWN)
            rec.last_error = str(exc)
            self._store.save(rec)
            self._audit(rec, "cancel_unknown", type(exc).__name__)
            return rec

        status = str(raw.get("status") or "").lower()
        if status in ("canceled", "cancelled"):
            self._set_state(rec, OrderState.CANCELLED)
        else:
            self._set_state(rec, OrderState.UNKNOWN)
        rec.updated_at_ms = now_ms()
        self._store.save(rec)
        self._audit(rec, "cancel_response", status)
        return rec

    def reconcile(self, execution_id: str) -> ExecutionRecord:
        """Reconcile local state against exchange (or paper broker).

        NEVER auto-resubmits. Resolves UNKNOWN via fetch.
        """
        rec = self._store.get(execution_id)
        if rec is None:
            raise ExecutionError(f"unknown execution_id={execution_id}")
        if is_terminal(rec.state) and rec.state is not OrderState.UNKNOWN:
            return rec

        prev = rec.state
        with suppress(TransitionError):
            self._set_state(rec, OrderState.RECONCILING)
        self._store.save(rec)
        self._audit(rec, "reconcile_start", f"from={prev.name}")

        raw: dict[str, object] | None = None
        try:
            if self._mode is ExecutionMode.PAPER:
                if rec.exchange_order_id:
                    raw = self._paper.fetch_order(rec.exchange_order_id, rec.symbol)
            else:
                if rec.exchange_order_id:
                    order = self._adapter.fetch_order(rec.exchange_order_id, rec.symbol)
                    raw = {
                        "id": order.id,
                        "status": order.status,
                        "filled": order.filled,
                        "remaining": order.remaining,
                        "average": order.price,
                        "price": order.price,
                        "timestamp": order.timestamp_ms,
                    }
        except Exception as exc:  # noqa: BLE001
            rec.last_error = str(exc)
            self._set_state(rec, OrderState.UNKNOWN)
            self._store.save(rec)
            self._audit(rec, "reconcile_failed", type(exc).__name__)
            return rec

        if raw is None:
            # Not found on exchange
            if prev in (OrderState.SUBMITTING, OrderState.UNKNOWN):
                # Never submitted or lost — mark FAILED, do not resubmit
                self._set_state(rec, OrderState.FAILED)
                rec.last_error = "order not found on exchange during reconcile"
            else:
                self._set_state(rec, OrderState.UNKNOWN)
            self._store.save(rec)
            self._audit(rec, "reconcile_missing", "")
            return rec

        return self._apply_exchange_response(rec, raw)

    def recover_on_startup(self) -> list[ExecutionRecord]:
        """Load non-terminal executions and reconcile. Never auto-submit."""
        active = self._store.list_active()
        results: list[ExecutionRecord] = []
        for rec in active:
            self._audit(rec, "startup_recover", f"state={rec.state.name}")
            if rec.state in (
                OrderState.SUBMITTING,
                OrderState.UNKNOWN,
                OrderState.SUBMITTED,
                OrderState.OPEN,
                OrderState.PARTIALLY_FILLED,
                OrderState.CANCEL_PENDING,
                OrderState.RECONCILING,
            ):
                results.append(self.reconcile(rec.execution_id))
            else:
                results.append(rec)
        return results

    def get(self, execution_id: str) -> ExecutionRecord | None:
        return self._store.get(execution_id)

    # --- internals ---

    def _set_state(self, rec: ExecutionRecord, target: OrderState) -> None:
        rec.state = transition(rec.state, target)
        rec.updated_at_ms = now_ms()

    def _reject_local(self, rec: ExecutionRecord, reason: str) -> ExecutionRecord:
        self._set_state(rec, OrderState.REJECTED)
        rec.last_error = reason
        self._store.save(rec)
        self._audit(rec, "rejected", reason)
        return rec

    def _audit(self, rec: ExecutionRecord, event: str, detail: str) -> None:
        # Sanitize accidental secret-like tokens
        safe = detail
        for token in ("apiKey", "api_key", "secret", "password", "authorization"):
            if token in safe.lower():
                safe = "[redacted]"
                break
        self._store.audit(
            correlation_id=rec.correlation_id,
            execution_id=rec.execution_id,
            event=event,
            detail=safe,
            state=rec.state.name,
        )
        logger.info(
            "exec event=%s id=%s state=%s detail=%s",
            event,
            rec.execution_id[:8],
            rec.state.name,
            safe[:120],
        )
