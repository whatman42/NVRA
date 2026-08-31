"""Structured market signal — calculation failure → NO_TRADE."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import time


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class MarketSignal:
    signal_id: str
    symbol: str
    timestamp: float
    direction: SignalDirection
    confidence: float
    regime: str
    reason: str
    data_quality: str
    strategy_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "regime": self.regime,
            "reason": self.reason,
            "data_quality": self.data_quality,
            "strategy_id": self.strategy_id,
            "metadata": dict(self.metadata),
        }


def build_signal(
    *,
    symbol: str,
    direction: SignalDirection,
    confidence: float,
    regime: str,
    reason: str,
    data_quality: str = "VALID",
    strategy_id: str = "tahap4_default",
    signal_id: Optional[str] = None,
    timestamp: Optional[float] = None,
) -> MarketSignal:
    ts = timestamp if timestamp is not None else time.time()
    sid = signal_id or f"sig-{symbol}-{int(ts * 1000)}"
    if data_quality not in ("VALID", "OK", "HEALTHY"):
        direction = SignalDirection.NO_TRADE
        reason = f"data_quality:{data_quality}"
    if regime in ("UNKNOWN", "UNCERTAIN", "MIXED", "TRANSITION"):
        direction = SignalDirection.NO_TRADE
        reason = f"regime_blocks:{regime}"
    if confidence < 0 or confidence > 1:
        direction = SignalDirection.NO_TRADE
        reason = "invalid_confidence"
    return MarketSignal(
        signal_id=sid,
        symbol=symbol,
        timestamp=ts,
        direction=direction,
        confidence=float(confidence),
        regime=regime,
        reason=reason,
        data_quality=data_quality,
        strategy_id=strategy_id,
    )
