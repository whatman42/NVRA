"""BridgeManager — orchestrates discovery, handshake, heartbeat, reconcile.

Does NOT implement trading strategy.
Later: will wrap as ExecutionProvider (Phase 3B continued).
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Sequence

from god.ipc.models import Message, MessageType, ConnectionState
from god.ipc.protocols import IPCTransport
from god.ipc.errors import IPCError

from .models import (
    TerminalInstance,
    BridgeHealth,
    BridgeConnectionState,
    Platform,
)
from .discovery import TerminalDiscovery
from .protocols import BridgeProtocol, build_hello
from .heartbeat import HeartbeatMonitor
from .reconciliation import Reconciler, ReconciliationReport
from .errors import HandshakeError, IncompatibleVersionError, BridgeError

logger = logging.getLogger(__name__)


class BridgeManager:
    """Manages one bridge connection to a terminal EA via IPCTransport."""

    def __init__(
        self,
        transport: IPCTransport,
        *,
        discovery: Optional[TerminalDiscovery] = None,
        protocol: Optional[BridgeProtocol] = None,
        terminal: Optional[TerminalInstance] = None,
        source: str = "brain",
        destination: str = "ea",
        heartbeat_interval_s: float = 2.0,
        max_missed_heartbeats: int = 3,
    ) -> None:
        self.transport = transport
        self.discovery = discovery or TerminalDiscovery()
        self.protocol = protocol or BridgeProtocol()
        self.terminal = terminal
        self.source = source
        self.destination = destination
        self._state = BridgeConnectionState.DISCONNECTED
        self._health = BridgeHealth(state=self._state)
        self._heartbeat = HeartbeatMonitor(
            transport,
            interval_s=heartbeat_interval_s,
            max_missed=max_missed_heartbeats,
            source=source,
            destination=destination,
        )
        self._reconciler = Reconciler(transport, source=source, destination=destination)
        self._instance_id: Optional[str] = None
        self._connected_at: Optional[float] = None
        self._last_report: Optional[ReconciliationReport] = None

    @property
    def state(self) -> BridgeConnectionState:
        return self._state

    @property
    def health(self) -> BridgeHealth:
        return self._health

    def discover_terminals(self) -> list[TerminalInstance]:
        return self.discovery.discover()

    def connect(self, timeout: float = 5.0) -> BridgeHealth:
        """Transport connect + HELLO handshake."""
        self._state = BridgeConnectionState.CONNECTING
        try:
            self.transport.connect(timeout=timeout)
        except IPCError as e:
            self._state = BridgeConnectionState.ERROR
            raise BridgeError(f"transport connect failed: {e}") from e

        self._state = BridgeConnectionState.HANDSHAKING
        hello = build_hello(
            source=self.source,
            destination=self.destination,
            platform=self.terminal.platform if self.terminal else None,
            terminal_id=self.terminal.terminal_id if self.terminal else None,
        )
        try:
            ack = self.transport.request(hello, timeout=timeout)
            info = self.protocol.validate_ack(ack, hello)
        except (IncompatibleVersionError, HandshakeError) as e:
            self._state = BridgeConnectionState.ERROR
            try:
                self.transport.disconnect()
            except Exception:
                pass
            raise
        except IPCError as e:
            self._state = BridgeConnectionState.ERROR
            raise HandshakeError(f"handshake transport error: {e}") from e

        self._instance_id = info.get("instance_id")
        self._connected_at = time.time()
        self._heartbeat.mark_connected()
        self._state = BridgeConnectionState.CONNECTED
        self._health = BridgeHealth(
            state=self._state,
            protocol_version=info.get("protocol_version"),
            bridge_version=info.get("bridge_version"),
            platform=info.get("platform"),
            terminal_id=info.get("terminal_id"),
            instance_id=self._instance_id,
        )
        logger.info(
            "Bridge connected: platform=%s instance=%s",
            self._health.platform,
            self._instance_id,
        )
        return self._health

    def disconnect(self) -> None:
        try:
            if self.transport.state != ConnectionState.DISCONNECTED:
                bye = Message.create(
                    message_type=MessageType.GOODBYE,
                    source=self.source,
                    destination=self.destination,
                    payload={},
                )
                try:
                    self.transport.send(bye)
                except Exception:
                    pass
        finally:
            try:
                self.transport.disconnect()
            except Exception:
                pass
            self._state = BridgeConnectionState.DISCONNECTED
            self._health = BridgeHealth(state=self._state)

    def heartbeat(self, timeout: float = 2.0) -> BridgeHealth:
        h = self._heartbeat.pulse(timeout=timeout)
        self._state = h.state
        self._health.state = h.state
        self._health.last_heartbeat = h.last_heartbeat
        self._health.heartbeat_latency_ms = h.heartbeat_latency_ms
        self._health.missed_heartbeats = h.missed_heartbeats
        if self._connected_at:
            self._health.connection_age_s = time.time() - self._connected_at
        return self._health

    def reconcile(
        self,
        brain_positions: Optional[Sequence[dict]] = None,
        brain_orders: Optional[Sequence[dict]] = None,
        timeout: float = 10.0,
    ) -> ReconciliationReport:
        prev = self._state
        self._state = BridgeConnectionState.RECONCILING
        try:
            report = self._reconciler.reconcile(
                brain_positions=brain_positions,
                brain_orders=brain_orders,
                timeout=timeout,
            )
            self._last_report = report
            self._state = BridgeConnectionState.HEALTHY
            self._health.state = self._state
            return report
        except Exception:
            self._state = prev
            raise

    def recover(
        self,
        brain_positions: Optional[Sequence[dict]] = None,
        brain_orders: Optional[Sequence[dict]] = None,
    ) -> dict:
        """Crash recovery path: reconnect → handshake → reconcile."""
        self._state = BridgeConnectionState.RECOVERING
        try:
            self.disconnect()
        except Exception:
            pass
        health = self.connect()
        report = self.reconcile(
            brain_positions=brain_positions,
            brain_orders=brain_orders,
        )
        return {
            "health": health.to_dict(),
            "reconciliation": report.to_dict(),
            "state": self._state.value,
        }
