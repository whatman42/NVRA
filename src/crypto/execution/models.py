"""Execution intent, fills, and audit records."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto

from crypto.execution.states import OrderState
from crypto.risk.models import RiskDecision, Side, TradeProposal


class ExecutionMode(Enum):
    PAPER = auto()
    LIVE = auto()


@dataclass(frozen=True, slots=True)
class Fill:
    fill_id: str
    quantity: float
    price: float
    fee_amount: float | None
    fee_currency: str | None
    timestamp_ms: int


@dataclass(slots=True)
class ExecutionRecord:
    """Mutable local execution state. Exchange is authoritative for truth."""

    execution_id: str
    client_order_id: str
    exchange_id: str
    account_id: str
    symbol: str
    side: Side
    order_type: str  # "market" | "limit"
    requested_quantity: float
    requested_price: float | None
    allowed_quantity: float
    allowed_notional: float
    state: OrderState
    exchange_order_id: str | None = None
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_fill_price: float | None = None
    fees_total: float = 0.0
    fee_currency: str | None = None
    fills: list[Fill] = field(default_factory=list)
    last_error: str | None = None
    created_at_ms: int = 0
    updated_at_ms: int = 0
    strategy_id: str = ""
    correlation_id: str = ""
    mode: ExecutionMode = ExecutionMode.PAPER

    def recompute_from_fills(self) -> None:
        if not self.fills:
            self.filled_quantity = 0.0
            self.average_fill_price = None
            self.fees_total = 0.0
            return
        total_qty = sum(f.quantity for f in self.fills)
        if total_qty <= 0:
            self.filled_quantity = 0.0
            self.average_fill_price = None
            return
        notional = sum(f.quantity * f.price for f in self.fills)
        self.filled_quantity = total_qty
        self.average_fill_price = notional / total_qty
        self.fees_total = sum(f.fee_amount or 0.0 for f in self.fills)
        self.remaining_quantity = max(0.0, self.allowed_quantity - total_qty)


def make_execution_id() -> str:
    return uuid.uuid4().hex


def make_client_order_id(
    exchange_id: str,
    account_id: str,
    symbol: str,
    side: Side,
    quantity: float,
    price: float | None,
    intent_key: str,
) -> str:
    """Deterministic client order id for idempotency.

    Same intent_key + order parameters → same client_order_id.
    """
    raw = f"{exchange_id}|{account_id}|{symbol}|{side.name}|{quantity:.12g}|{price}|{intent_key}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"c{digest}"


def make_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass(frozen=True, slots=True)
class AuditEvent:
    timestamp_ms: int
    correlation_id: str
    execution_id: str
    event: str
    detail: str
    state: str | None = None


def now_ms() -> int:
    return int(time.time() * 1000)


def record_from_decision(
    decision: RiskDecision,
    *,
    order_type: str,
    mode: ExecutionMode,
    intent_key: str,
    correlation_id: str | None = None,
) -> ExecutionRecord:
    """Build an ExecutionRecord from an approved RiskDecision."""
    if decision.proposal is None:
        raise ValueError("RiskDecision missing proposal")
    prop: TradeProposal = decision.proposal
    ts = now_ms()
    cid = correlation_id or make_correlation_id()
    client_oid = make_client_order_id(
        prop.exchange_id,
        prop.account_id,
        prop.symbol,
        prop.side,
        decision.allowed_quantity,
        prop.requested_price,
        intent_key,
    )
    return ExecutionRecord(
        execution_id=make_execution_id(),
        client_order_id=client_oid,
        exchange_id=prop.exchange_id,
        account_id=prop.account_id,
        symbol=prop.symbol,
        side=prop.side,
        order_type=order_type,
        requested_quantity=prop.requested_quantity,
        requested_price=prop.requested_price,
        allowed_quantity=decision.allowed_quantity,
        allowed_notional=decision.allowed_notional,
        state=OrderState.RISK_APPROVED,
        remaining_quantity=decision.allowed_quantity,
        created_at_ms=ts,
        updated_at_ms=ts,
        strategy_id=prop.strategy_id,
        correlation_id=cid,
        mode=mode,
    )
