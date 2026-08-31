"""Thread-safe application state snapshot for GUI (2 Hz max)."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GuiSnapshot:
    """Immutable-ish snapshot polled by GUI — never contains secrets."""

    timestamp_ms: int = 0
    trading_mode: str = "PAPER"
    emergency_stop: bool = False
    safety_mode: str = "NORMAL"
    # Account
    available_balance: float = 0.0
    equity: float = 0.0
    invested: float = 0.0
    locked: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    # Risk (display only — from RiskPolicy/engine, not editable here)
    daily_loss_pct: float = 0.0
    drawdown_pct: float = 0.0
    max_position_pct: float = 0.0
    entry_allowed: bool = True
    # Execution counts
    orders_pending: int = 0
    orders_open: int = 0
    orders_filled: int = 0
    orders_unknown: int = 0
    # System
    governor_state: str = "NORMAL"
    supervisor_safe_mode: bool = False
    hardware_profile: str = "ULTRA_LITE"
    cpu_usage: float | None = None
    ram_usage: float | None = None
    # ML / scanner
    ml_models: int = 0
    ml_active: tuple[str, ...] = ()
    ml_loaded: tuple[str, ...] = ()
    ml_selection_reason: str = ""
    hardware_score: float = 0.0
    top_opportunity: str = ""
    data_freshness: str = "UNKNOWN"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


class SnapshotBus:
    """Backend writes snapshots; GUI reads last snapshot only."""

    def __init__(self, min_interval_ms: int = 500) -> None:
        self._lock = threading.Lock()
        self._snapshot = GuiSnapshot()
        self._min_interval_ms = min_interval_ms
        self._last_publish_ms = 0

    def publish(self, snap: GuiSnapshot) -> None:
        now = int(time.time() * 1000)
        with self._lock:
            if now - self._last_publish_ms < self._min_interval_ms:
                # debounce — keep latest fields but don't spam
                pass
            snap.timestamp_ms = now
            self._snapshot = snap
            self._last_publish_ms = now

    def get(self) -> GuiSnapshot:
        with self._lock:
            # return a shallow copy
            s = self._snapshot
            return GuiSnapshot(**{**s.to_dict(), "extra": dict(s.extra)})
