"""Websocket/stream health state machine — no trading until HEALTHY."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import time


class StreamState(str, Enum):
    CONNECTED = "CONNECTED"
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    RESYNC = "RESYNC"


@dataclass
class StreamHealth:
    state: StreamState = StreamState.DISCONNECTED
    last_message_ts: float = 0.0
    last_sequence: Optional[int] = None
    reconnect_attempts: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def allows_new_entry(self) -> bool:
        return self.state == StreamState.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "allows_new_entry": self.allows_new_entry,
            "last_message_ts": self.last_message_ts,
            "last_sequence": self.last_sequence,
            "reconnect_attempts": self.reconnect_attempts,
            "reasons": list(self.reasons),
        }


class StreamHealthMonitor:
    def __init__(self, stale_after_seconds: float = 15.0) -> None:
        self.stale_after_seconds = stale_after_seconds
        self.health = StreamHealth()

    def on_connected(self) -> StreamHealth:
        self.health.state = StreamState.CONNECTED
        self.health.reasons = []
        return self.health

    def on_message(self, *, sequence: Optional[int] = None, ts: Optional[float] = None) -> StreamHealth:
        now = ts if ts is not None else time.time()
        self.health.last_message_ts = now
        if sequence is not None:
            if self.health.last_sequence is not None and sequence < self.health.last_sequence:
                self.health.state = StreamState.RESYNC
                self.health.reasons = ["out_of_order"]
            elif self.health.last_sequence is not None and sequence > self.health.last_sequence + 1:
                self.health.state = StreamState.RESYNC
                self.health.reasons = ["sequence_gap"]
            else:
                self.health.state = StreamState.HEALTHY
                self.health.reasons = []
            self.health.last_sequence = sequence
        else:
            self.health.state = StreamState.HEALTHY
            self.health.reasons = []
        return self.health

    def on_disconnect(self) -> StreamHealth:
        self.health.state = StreamState.DISCONNECTED
        self.health.reasons = ["disconnect"]
        return self.health

    def on_reconnect_start(self) -> StreamHealth:
        self.health.state = StreamState.RECONNECTING
        self.health.reconnect_attempts += 1
        self.health.reasons = ["reconnecting"]
        return self.health

    def tick(self, *, now: Optional[float] = None) -> StreamHealth:
        now = now if now is not None else time.time()
        if self.health.state in (StreamState.HEALTHY, StreamState.CONNECTED, StreamState.RESYNC):
            if self.health.last_message_ts and (now - self.health.last_message_ts) > self.stale_after_seconds:
                self.health.state = StreamState.STALE
                self.health.reasons = ["stale_stream"]
        return self.health
