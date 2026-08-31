"""Typed domain models for persistent memory.

These are pure data containers — no trading logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import json
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def _dumps(obj: Any) -> str:
    if obj is None:
        return "null"
    return json.dumps(obj, default=str)


def _loads(s: Optional[str]) -> Any:
    if s is None or s == "":
        return {}
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}


@dataclass
class Strategy:
    strategy_id: str
    name: str
    status: str = "GENERATED"
    parent_id: Optional[str] = None
    generation: int = 0
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def create(name: str, **kw: Any) -> "Strategy":
        from .database import utc_now
        now = utc_now()
        return Strategy(
            strategy_id=kw.get("strategy_id") or new_id(),
            name=name,
            status=kw.get("status", "GENERATED"),
            parent_id=kw.get("parent_id"),
            generation=kw.get("generation", 0),
            created_at=kw.get("created_at", now),
            updated_at=kw.get("updated_at", now),
            metadata=kw.get("metadata") or {},
        )


@dataclass
class StrategyVersion:
    version_id: str
    strategy_id: str
    version_num: int
    genome: dict = field(default_factory=dict)
    lineage: dict = field(default_factory=dict)
    created_at: str = ""

    @staticmethod
    def create(strategy_id: str, version_num: int, genome: dict, **kw: Any) -> "StrategyVersion":
        from .database import utc_now
        return StrategyVersion(
            version_id=kw.get("version_id") or new_id(),
            strategy_id=strategy_id,
            version_num=version_num,
            genome=genome,
            lineage=kw.get("lineage") or {},
            created_at=kw.get("created_at", utc_now()),
        )


@dataclass
class Observation:
    observation_id: str
    timestamp: str
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    market_state: dict = field(default_factory=dict)
    features: dict = field(default_factory=dict)
    regime: Optional[str] = None
    source: Optional[str] = None
    content_hash: Optional[str] = None
    created_at: str = ""

    @staticmethod
    def create(**kw: Any) -> "Observation":
        from .database import utc_now
        now = utc_now()
        return Observation(
            observation_id=kw.get("observation_id") or new_id(),
            timestamp=kw.get("timestamp", now),
            symbol=kw.get("symbol"),
            timeframe=kw.get("timeframe"),
            market_state=kw.get("market_state") or {},
            features=kw.get("features") or {},
            regime=kw.get("regime"),
            source=kw.get("source"),
            content_hash=kw.get("content_hash"),
            created_at=kw.get("created_at", now),
        )


@dataclass
class Decision:
    decision_id: str
    timestamp: str
    action: str
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    strategy_id: Optional[str] = None
    strategy_version: Optional[int] = None
    policy_version: Optional[str] = None
    volume: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    confidence: Optional[float] = None
    regime: Optional[str] = None
    reasoning: dict = field(default_factory=dict)
    observation_id: Optional[str] = None
    created_at: str = ""

    @staticmethod
    def create(action: str, **kw: Any) -> "Decision":
        from .database import utc_now
        now = utc_now()
        return Decision(
            decision_id=kw.get("decision_id") or new_id(),
            timestamp=kw.get("timestamp", now),
            action=action,
            symbol=kw.get("symbol"),
            timeframe=kw.get("timeframe"),
            strategy_id=kw.get("strategy_id"),
            strategy_version=kw.get("strategy_version"),
            policy_version=kw.get("policy_version"),
            volume=kw.get("volume"),
            sl=kw.get("sl"),
            tp=kw.get("tp"),
            confidence=kw.get("confidence"),
            regime=kw.get("regime"),
            reasoning=kw.get("reasoning") or {},
            observation_id=kw.get("observation_id"),
            created_at=kw.get("created_at", now),
        )


@dataclass
class Trade:
    trade_id: str
    symbol: str
    side: str
    volume: float
    status: str = "OPEN"
    decision_id: Optional[str] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    pnl: Optional[float] = None
    fees: float = 0.0
    spread: Optional[float] = None
    slippage: Optional[float] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None
    holding_time_sec: Optional[float] = None
    broker_ticket: Optional[str] = None
    strategy_id: Optional[str] = None
    strategy_version: Optional[int] = None
    is_virtual: bool = False
    metadata: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def create(symbol: str, side: str, volume: float, **kw: Any) -> "Trade":
        from .database import utc_now
        now = utc_now()
        return Trade(
            trade_id=kw.get("trade_id") or new_id(),
            symbol=symbol, side=side, volume=volume,
            status=kw.get("status", "OPEN"),
            decision_id=kw.get("decision_id"),
            entry_price=kw.get("entry_price"),
            exit_price=kw.get("exit_price"),
            sl=kw.get("sl"), tp=kw.get("tp"),
            opened_at=kw.get("opened_at", now),
            closed_at=kw.get("closed_at"),
            pnl=kw.get("pnl"), fees=kw.get("fees", 0.0),
            spread=kw.get("spread"), slippage=kw.get("slippage"),
            mae=kw.get("mae"), mfe=kw.get("mfe"),
            holding_time_sec=kw.get("holding_time_sec"),
            broker_ticket=kw.get("broker_ticket"),
            strategy_id=kw.get("strategy_id"),
            strategy_version=kw.get("strategy_version"),
            is_virtual=kw.get("is_virtual", False),
            metadata=kw.get("metadata") or {},
            created_at=kw.get("created_at", now),
            updated_at=kw.get("updated_at", now),
        )


@dataclass
class Position:
    position_id: str
    symbol: str
    side: str
    volume: float
    opened_at: str
    status: str = "OPEN"
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    broker_ticket: Optional[str] = None
    strategy_id: Optional[str] = None
    updated_at: str = ""
    is_virtual: bool = False
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def create(symbol: str, side: str, volume: float, **kw: Any) -> "Position":
        from .database import utc_now
        now = utc_now()
        return Position(
            position_id=kw.get("position_id") or new_id(),
            symbol=symbol, side=side, volume=volume,
            opened_at=kw.get("opened_at", now),
            status=kw.get("status", "OPEN"),
            entry_price=kw.get("entry_price"),
            current_price=kw.get("current_price"),
            sl=kw.get("sl"), tp=kw.get("tp"),
            unrealized_pnl=kw.get("unrealized_pnl"),
            broker_ticket=kw.get("broker_ticket"),
            strategy_id=kw.get("strategy_id"),
            updated_at=kw.get("updated_at", now),
            is_virtual=kw.get("is_virtual", False),
            metadata=kw.get("metadata") or {},
        )


@dataclass
class Experience:
    experience_id: str
    timestamp: str
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    market_state: dict = field(default_factory=dict)
    features: dict = field(default_factory=dict)
    regime: Optional[str] = None
    strategy_id: Optional[str] = None
    strategy_version: Optional[int] = None
    action: Optional[str] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    position_size: Optional[float] = None
    fees: Optional[float] = None
    spread: Optional[float] = None
    slippage: Optional[float] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None
    holding_time_sec: Optional[float] = None
    pnl: Optional[float] = None
    reward: Optional[float] = None
    outcome: Optional[str] = None
    policy_version: Optional[str] = None
    trade_id: Optional[str] = None
    is_virtual: bool = False
    created_at: str = ""

    @staticmethod
    def create(**kw: Any) -> "Experience":
        from .database import utc_now
        now = utc_now()
        return Experience(
            experience_id=kw.get("experience_id") or new_id(),
            timestamp=kw.get("timestamp", now),
            symbol=kw.get("symbol"), timeframe=kw.get("timeframe"),
            market_state=kw.get("market_state") or {},
            features=kw.get("features") or {},
            regime=kw.get("regime"),
            strategy_id=kw.get("strategy_id"),
            strategy_version=kw.get("strategy_version"),
            action=kw.get("action"),
            entry_price=kw.get("entry_price"), exit_price=kw.get("exit_price"),
            sl=kw.get("sl"), tp=kw.get("tp"),
            position_size=kw.get("position_size"),
            fees=kw.get("fees"), spread=kw.get("spread"), slippage=kw.get("slippage"),
            mae=kw.get("mae"), mfe=kw.get("mfe"),
            holding_time_sec=kw.get("holding_time_sec"),
            pnl=kw.get("pnl"), reward=kw.get("reward"),
            outcome=kw.get("outcome"), policy_version=kw.get("policy_version"),
            trade_id=kw.get("trade_id"), is_virtual=kw.get("is_virtual", False),
            created_at=kw.get("created_at", now),
        )
