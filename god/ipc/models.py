"""IPC message envelope and connection state.

All brain \u2194 EA communication uses this envelope.
No credentials, no strategy payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import json
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


class MessageType(str, Enum):
    HELLO = "HELLO"
    HELLO_ACK = "HELLO_ACK"
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    ACCOUNT_STATE = "ACCOUNT_STATE"
    MARKET_STATE = "MARKET_STATE"
    POSITION_STATE = "POSITION_STATE"
    ORDER_STATE = "ORDER_STATE"
    EXECUTE_REQUEST = "EXECUTE_REQUEST"
    EXECUTE_RESPONSE = "EXECUTE_RESPONSE"
    CANCEL_REQUEST = "CANCEL_REQUEST"
    CANCEL_RESPONSE = "CANCEL_RESPONSE"
    RECONCILE_REQUEST = "RECONCILE_REQUEST"
    RECONCILE_RESPONSE = "RECONCILE_RESPONSE"
    ERROR = "ERROR"
    GOODBYE = "GOODBYE"
    INCOMPATIBLE_VERSION = "INCOMPATIBLE_VERSION"


class ConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"


PROTOCOL_VERSION = "GOD-BRIDGE/1"


@dataclass
class Message:
    """Versioned message envelope for all IPC traffic."""

    protocol_version: str
    message_type: MessageType
    request_id: str
    timestamp: str
    source: str
    destination: str
    payload: dict = field(default_factory=dict)
    correlation_id: Optional[str] = None
    sequence: int = 0

    def to_dict(self) -> dict:
        return {
            "protocol_version": self.protocol_version,
            "message_type": self.message_type.value
            if isinstance(self.message_type, MessageType)
            else self.message_type,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "destination": self.destination,
            "sequence": self.sequence,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @staticmethod
    def from_dict(data: dict) -> "Message":
        if not isinstance(data, dict):
            raise ValueError("message must be a dict")
        mt = data.get("message_type")
        if mt is None:
            raise ValueError("missing message_type")
        try:
            message_type = MessageType(mt)
        except ValueError as e:
            raise ValueError(f"unknown message_type: {mt}") from e
        return Message(
            protocol_version=str(data.get("protocol_version") or ""),
            message_type=message_type,
            request_id=str(data.get("request_id") or ""),
            correlation_id=data.get("correlation_id"),
            timestamp=str(data.get("timestamp") or ""),
            source=str(data.get("source") or ""),
            destination=str(data.get("destination") or ""),
            sequence=int(data.get("sequence") or 0),
            payload=dict(data.get("payload") or {}),
        )

    @staticmethod
    def from_json(raw: str) -> "Message":
        data = json.loads(raw)
        return Message.from_dict(data)

    @staticmethod
    def create(
        message_type: MessageType,
        source: str,
        destination: str,
        payload: Optional[dict] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        sequence: int = 0,
        protocol_version: str = PROTOCOL_VERSION,
        timestamp: Optional[str] = None,
    ) -> "Message":
        from god.memory.database import utc_now

        return Message(
            protocol_version=protocol_version,
            message_type=message_type,
            request_id=request_id or new_id(),
            correlation_id=correlation_id,
            timestamp=timestamp or utc_now(),
            source=source,
            destination=destination,
            sequence=sequence,
            payload=payload or {},
        )
