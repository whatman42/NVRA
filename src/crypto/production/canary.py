"""Micro-capital LIVE canary state machine — explicit operator-driven, not auto-profit."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class CanaryPhase(Enum):
    IDLE = auto()
    BUY_PENDING = auto()
    BUY_FILLED = auto()
    HOLDING = auto()
    SELL_PENDING = auto()
    SELL_FILLED = auto()
    RECONCILED = auto()
    FAILED = auto()
    BLOCKED = auto()


@dataclass
class CanaryState:
    """Tracks first LIVE round-trip: BUY → verify → HOLD → SELL → verify → reconcile."""

    phase: CanaryPhase = CanaryPhase.IDLE
    buy_execution_id: str | None = None
    sell_execution_id: str | None = None
    buy_filled: bool = False
    sell_filled: bool = False
    reconciled: bool = False
    last_error: str = ""
    events: list[str] = field(default_factory=list)

    def note(self, event: str) -> None:
        self.events.append(event)

    def fail(self, reason: str) -> None:
        self.phase = CanaryPhase.FAILED
        self.last_error = reason
        self.note(f"FAILED:{reason}")

    def mark_buy_submitted(self, execution_id: str) -> None:
        self.buy_execution_id = execution_id
        self.phase = CanaryPhase.BUY_PENDING
        self.note("buy_submitted")

    def mark_buy_filled(self) -> None:
        self.buy_filled = True
        self.phase = CanaryPhase.BUY_FILLED
        self.note("buy_filled")
        self.phase = CanaryPhase.HOLDING
        self.note("holding")

    def mark_sell_submitted(self, execution_id: str) -> None:
        self.sell_execution_id = execution_id
        self.phase = CanaryPhase.SELL_PENDING
        self.note("sell_submitted")

    def mark_sell_filled(self) -> None:
        self.sell_filled = True
        self.phase = CanaryPhase.SELL_FILLED
        self.note("sell_filled")

    def mark_reconciled(self) -> None:
        if self.buy_filled and self.sell_filled:
            self.reconciled = True
            self.phase = CanaryPhase.RECONCILED
            self.note("reconciled")
        else:
            self.fail("reconcile_incomplete")

    @property
    def round_trip_ok(self) -> bool:
        return self.phase is CanaryPhase.RECONCILED and self.reconciled
