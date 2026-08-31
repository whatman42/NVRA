"""Market data chaos — stale, duplicate, missing candles, reconnect bursts."""

from __future__ import annotations

from dataclasses import dataclass, field

from crypto.governor.freshness import MarketDataFreshnessGate
from crypto.governor.states import DataFreshness


@dataclass
class MarketDataChaos:
    """Controls synthetic market-data quality for tests."""

    last_update_ms: int | None = None
    duplicate_candles: int = 0
    missing_candles: int = 0
    reconnect_count: int = 0
    burst_events: list[str] = field(default_factory=list)

    def mark_update(self, ts_ms: int) -> None:
        self.last_update_ms = ts_ms

    def inject_stale(self) -> None:
        self.last_update_ms = 0

    def inject_duplicate(self) -> None:
        self.duplicate_candles += 1
        self.burst_events.append("duplicate")

    def inject_missing(self, n: int = 1) -> None:
        self.missing_candles += n
        self.burst_events.append(f"missing:{n}")

    def inject_disconnect(self) -> None:
        self.reconnect_count += 1
        self.burst_events.append("disconnect")

    def freshness(self, gate: MarketDataFreshnessGate, *, now_ms: int) -> DataFreshness:
        return gate.evaluate(self.last_update_ms, now_ms=now_ms)

    def allow_proposal(self, gate: MarketDataFreshnessGate, *, now_ms: int) -> bool:
        return gate.allow_new_proposal(self.freshness(gate, now_ms=now_ms))
