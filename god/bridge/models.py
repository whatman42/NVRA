"""Typed models for terminal instances and bridge health.

No credentials stored. No strategy fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


class Platform(str, Enum):
    MT4 = "MT4"
    MT5 = "MT5"
    UNKNOWN = "UNKNOWN"


class TerminalStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    UNKNOWN = "UNKNOWN"


class BridgeConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    HANDSHAKING = "HANDSHAKING"
    CONNECTED = "CONNECTED"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECONCILING = "RECONCILING"
    RECOVERING = "RECOVERING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class TerminalInstance:
    """One discovered MT4 or MT5 terminal instance."""

    terminal_id: str
    platform: Platform
    executable_path: Optional[str] = None
    data_path: Optional[str] = None
    experts_path: Optional[str] = None
    version: Optional[str] = None
    build: Optional[str] = None
    process_id: Optional[int] = None
    status: TerminalStatus = TerminalStatus.UNKNOWN
    discovered_at: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def create(
        platform: Platform | str,
        *,
        executable_path: Optional[str] = None,
        data_path: Optional[str] = None,
        experts_path: Optional[str] = None,
        version: Optional[str] = None,
        build: Optional[str] = None,
        process_id: Optional[int] = None,
        status: TerminalStatus | str = TerminalStatus.DISCOVERED,
        metadata: Optional[dict] = None,
        terminal_id: Optional[str] = None,
        discovered_at: Optional[str] = None,
    ) -> "TerminalInstance":
        from god.memory.database import utc_now

        plat = platform if isinstance(platform, Platform) else Platform(platform)
        st = status if isinstance(status, TerminalStatus) else TerminalStatus(status)
        return TerminalInstance(
            terminal_id=terminal_id or new_id(),
            platform=plat,
            executable_path=executable_path,
            data_path=data_path,
            experts_path=experts_path,
            version=version,
            build=build,
            process_id=process_id,
            status=st,
            discovered_at=discovered_at or utc_now(),
            metadata=metadata or {},
        )


@dataclass
class BridgeHealth:
    """Application-level health of a bridge connection."""

    state: BridgeConnectionState = BridgeConnectionState.DISCONNECTED
    last_heartbeat: Optional[str] = None
    heartbeat_latency_ms: Optional[float] = None
    missed_heartbeats: int = 0
    connection_age_s: Optional[float] = None
    protocol_version: Optional[str] = None
    bridge_version: Optional[str] = None
    platform: Optional[str] = None
    terminal_id: Optional[str] = None
    instance_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "last_heartbeat": self.last_heartbeat,
            "heartbeat_latency_ms": self.heartbeat_latency_ms,
            "missed_heartbeats": self.missed_heartbeats,
            "connection_age_s": self.connection_age_s,
            "protocol_version": self.protocol_version,
            "bridge_version": self.bridge_version,
            "platform": self.platform,
            "terminal_id": self.terminal_id,
            "instance_id": self.instance_id,
            "metadata": dict(self.metadata),
        }
