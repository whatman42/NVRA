"""Runtime models for Agent Skeleton (Phase 3).

These complement the persistent memory models.
No trading strategy logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


class LifecycleState(str, Enum):
    """Persistent agent lifecycle states."""
    CREATED = "CREATED"
    READY = "READY"
    OBSERVING = "OBSERVING"
    DECIDING = "DECIDING"
    EXECUTING = "EXECUTING"
    MEASURING = "MEASURING"
    LEARNING = "LEARNING"
    CRASH = "CRASH"
    RECOVERY = "RECOVERY"
    RECONCILIATION = "RECONCILIATION"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class ActionType(str, Enum):
    """Allowed decision actions — policy that chooses them is NOT Phase 3."""
    NO_ACTION = "NO_ACTION"
    OBSERVE_ONLY = "OBSERVE_ONLY"
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    MODIFY = "MODIFY"


@dataclass(frozen=True)
class AccountState:
    """Snapshot of account balances / equity (provider-agnostic)."""
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    currency: str = "USD"
    leverage: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MarketState:
    """Minimal market snapshot — no indicators or strategy signals."""
    symbol: Optional[str] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    timestamp: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeObservation:
    """Immutable observation produced by the Observer component.

    Answers only: 'What is happening right now?'
    Does not contain decisions or strategy logic.
    Maps to memory.Observation for persistence.
    """
    observation_id: str
    timestamp: str
    source: str
    environment: str  # e.g. "null", "virtual", "mt5"
    account_state: AccountState
    market_state: MarketState
    positions: tuple  # tuple of Position-like dicts or memory Position
    capabilities: tuple = ()
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def create(
        source: str,
        environment: str,
        account_state: AccountState,
        market_state: MarketState,
        positions: list | tuple = (),
        capabilities: list | tuple = (),
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
        observation_id: Optional[str] = None,
    ) -> "RuntimeObservation":
        from god.memory.database import utc_now
        return RuntimeObservation(
            observation_id=observation_id or new_id(),
            timestamp=timestamp or utc_now(),
            source=source,
            environment=environment,
            account_state=account_state,
            market_state=market_state,
            positions=tuple(positions),
            capabilities=tuple(capabilities),
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class RuntimeDecision:
    """Typed decision produced by the Decider.

    Phase 3 does NOT hard-code when to OPEN/CLOSE.
    The default policy returns NO_ACTION so that intelligence
    can be introduced later via research / evolution layers.
    """
    decision_id: str
    observation_id: str
    action: ActionType
    timestamp: str
    rationale: str = ""
    confidence: Optional[float] = None
    policy_version: str = "phase3-stub-v0"
    symbol: Optional[str] = None
    volume: Optional[float] = None
    side: Optional[str] = None  # BUY / SELL when action=OPEN
    sl: Optional[float] = None
    tp: Optional[float] = None
    position_id: Optional[str] = None  # for CLOSE / MODIFY
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def create(
        observation_id: str,
        action: ActionType = ActionType.NO_ACTION,
        rationale: str = "default stub policy — no strategy intelligence",
        **kw: Any,
    ) -> "RuntimeDecision":
        from god.memory.database import utc_now
        return RuntimeDecision(
            decision_id=kw.get("decision_id") or new_id(),
            observation_id=observation_id,
            action=action if isinstance(action, ActionType) else ActionType(action),
            timestamp=kw.get("timestamp") or utc_now(),
            rationale=rationale,
            confidence=kw.get("confidence"),
            policy_version=kw.get("policy_version", "phase3-stub-v0"),
            symbol=kw.get("symbol"),
            volume=kw.get("volume"),
            side=kw.get("side"),
            sl=kw.get("sl"),
            tp=kw.get("tp"),
            position_id=kw.get("position_id"),
            metadata=kw.get("metadata") or {},
        )


@dataclass(frozen=True)
class ExecutionRequest:
    """Request submitted to an ExecutionProvider.

    request_id is the idempotency key.
    """
    request_id: str
    decision_id: str
    action: ActionType
    symbol: Optional[str] = None
    volume: Optional[float] = None
    side: Optional[str] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    position_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def from_decision(d: RuntimeDecision, request_id: Optional[str] = None) -> "ExecutionRequest":
        return ExecutionRequest(
            request_id=request_id or new_id(),
            decision_id=d.decision_id,
            action=d.action,
            symbol=d.symbol,
            volume=d.volume,
            side=d.side,
            sl=d.sl,
            tp=d.tp,
            position_id=d.position_id,
            metadata=dict(d.metadata),
        )


@dataclass(frozen=True)
class ExecutionResult:
    """What the ExecutionProvider actually did (or refused to do)."""
    request_id: str
    decision_id: str
    success: bool
    executed_action: ActionType
    timestamp: str
    order_id: Optional[str] = None
    position_id: Optional[str] = None
    fill_price: Optional[float] = None
    volume: Optional[float] = None
    fees: float = 0.0
    slippage: float = 0.0
    message: str = ""
    is_duplicate: bool = False  # True when idempotency short-circuited
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def create(
        request_id: str,
        decision_id: str,
        success: bool,
        executed_action: ActionType,
        **kw: Any,
    ) -> "ExecutionResult":
        from god.memory.database import utc_now
        return ExecutionResult(
            request_id=request_id,
            decision_id=decision_id,
            success=success,
            executed_action=executed_action if isinstance(executed_action, ActionType) else ActionType(executed_action),
            timestamp=kw.get("timestamp") or utc_now(),
            order_id=kw.get("order_id"),
            position_id=kw.get("position_id"),
            fill_price=kw.get("fill_price"),
            volume=kw.get("volume"),
            fees=kw.get("fees", 0.0),
            slippage=kw.get("slippage", 0.0),
            message=kw.get("message", ""),
            is_duplicate=kw.get("is_duplicate", False),
            metadata=kw.get("metadata") or {},
        )


@dataclass(frozen=True)
class Measurement:
    """Separates 'what was decided' from 'what actually happened'."""
    measurement_id: str
    decision_id: str
    request_id: str
    timestamp: str
    requested_action: ActionType
    executed_action: ActionType
    success: bool
    latency_ms: float = 0.0
    fill_price: Optional[float] = None
    slippage: float = 0.0
    fees: float = 0.0
    position_delta: float = 0.0
    pnl: Optional[float] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def from_result(
        decision: RuntimeDecision,
        result: ExecutionResult,
        latency_ms: float = 0.0,
        **kw: Any,
    ) -> "Measurement":
        from god.memory.database import utc_now
        return Measurement(
            measurement_id=kw.get("measurement_id") or new_id(),
            decision_id=decision.decision_id,
            request_id=result.request_id,
            timestamp=kw.get("timestamp") or utc_now(),
            requested_action=decision.action,
            executed_action=result.executed_action,
            success=result.success,
            latency_ms=latency_ms,
            fill_price=result.fill_price,
            slippage=result.slippage,
            fees=result.fees,
            position_delta=kw.get("position_delta", 0.0),
            pnl=kw.get("pnl"),
            error=None if result.success else result.message,
            metadata=kw.get("metadata") or {},
        )


@dataclass(frozen=True)
class LearningResult:
    """Placeholder result of the LearningEngine interface.

    Phase 3 only provides the contract; no real learning occurs.
    """
    learning_id: str
    timestamp: str
    experiences_recorded: int = 0
    notes: str = "learning interface only — no model update in Phase 3"
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def create(experiences_recorded: int = 0, **kw: Any) -> "LearningResult":
        from god.memory.database import utc_now
        return LearningResult(
            learning_id=kw.get("learning_id") or new_id(),
            timestamp=kw.get("timestamp") or utc_now(),
            experiences_recorded=experiences_recorded,
            notes=kw.get("notes", "learning interface only — no model update in Phase 3"),
            metadata=kw.get("metadata") or {},
        )
