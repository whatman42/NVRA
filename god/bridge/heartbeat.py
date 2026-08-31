"""Application-level heartbeat for bridge connections.

Does not rely solely on TCP socket liveness.
"""

from __future__ import annotations

import time
from typing import Optional

from god.ipc.models import Message, MessageType, ConnectionState
from god.ipc.protocols import IPCTransport
from .models import BridgeHealth, BridgeConnectionState
from god.memory.database import utc_now


class HeartbeatMonitor:
    """Tracks missed heartbeats and latency."""

    def __init__(
        self,
        transport: IPCTransport,
        *,
        interval_s: float = 2.0,
        max_missed: int = 3,
        source: str = "brain",
        destination: str = "ea",
    ) -> None:
        self.transport = transport
        self.interval_s = interval_s
        self.max_missed = max_missed
        self.source = source
        self.destination = destination
        self.missed = 0
        self.last_latency_ms: Optional[float] = None
        self.last_heartbeat_at: Optional[str] = None
        self._connected_since: Optional[float] = None

    def mark_connected(self) -> None:
        self._connected_since = time.time()
        self.missed = 0

    def pulse(self, timeout: float = 2.0) -> BridgeHealth:
        """Send HEARTBEAT and wait for HEARTBEAT_ACK."""
        if self._connected_since is None:
            self.mark_connected()
        msg = Message.create(
            message_type=MessageType.HEARTBEAT,
            source=self.source,
            destination=self.destination,
            payload={"t": time.time()},
        )
        t0 = time.perf_counter()
        try:
            resp = self.transport.request(msg, timeout=timeout)
            latency = (time.perf_counter() - t0) * 1000.0
            if resp.message_type != MessageType.HEARTBEAT_ACK:
                self.missed += 1
            else:
                self.missed = 0
                self.last_latency_ms = latency
                self.last_heartbeat_at = utc_now()
        except Exception:
            self.missed += 1
            latency = None

        state = BridgeConnectionState.HEALTHY
        if self.missed >= self.max_missed:
            state = BridgeConnectionState.DISCONNECTED
        elif self.missed > 0:
            state = BridgeConnectionState.DEGRADED

        age = (time.time() - self._connected_since) if self._connected_since else None
        return BridgeHealth(
            state=state,
            last_heartbeat=self.last_heartbeat_at,
            heartbeat_latency_ms=self.last_latency_ms,
            missed_heartbeats=self.missed,
            connection_age_s=age,
        )

    def build_ack(self, heartbeat: Message) -> Message:
        return Message.create(
            message_type=MessageType.HEARTBEAT_ACK,
            source=self.destination,
            destination=self.source,
            payload={"t": time.time(), "echo": heartbeat.payload.get("t")},
            correlation_id=heartbeat.request_id,
            request_id=heartbeat.request_id,
        )
