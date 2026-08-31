"""Bridge protocol helpers — HELLO, version negotiation, envelope builders.

Protocol: GOD-BRIDGE/1
No trading intelligence.
"""

from __future__ import annotations

from typing import Optional

from god.ipc.models import Message, MessageType, PROTOCOL_VERSION, new_id
from .models import TerminalInstance, Platform
from .errors import IncompatibleVersionError, HandshakeError


SUPPORTED_PROTOCOLS = (PROTOCOL_VERSION,)
BRIDGE_VERSION = "3b-a.0.1"


def build_hello(
    *,
    source: str = "brain",
    destination: str = "ea",
    platform: Optional[Platform | str] = None,
    terminal_id: Optional[str] = None,
    instance_id: Optional[str] = None,
    capabilities: Optional[list] = None,
) -> Message:
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "bridge_version": BRIDGE_VERSION,
        "platform": platform.value if isinstance(platform, Platform) else platform,
        "terminal_id": terminal_id,
        "instance_id": instance_id or new_id(),
        "capabilities": capabilities or ["execute", "state", "heartbeat", "reconcile"],
        "nonce": new_id(),
    }
    return Message.create(
        message_type=MessageType.HELLO,
        source=source,
        destination=destination,
        payload=payload,
    )


def build_hello_ack(
    hello: Message,
    *,
    source: str = "ea",
    destination: str = "brain",
    accepted: bool = True,
    platform: Optional[str] = None,
    terminal_id: Optional[str] = None,
    instance_id: Optional[str] = None,
    bridge_version: str = BRIDGE_VERSION,
) -> Message:
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "bridge_version": bridge_version,
        "accepted": accepted,
        "platform": platform,
        "terminal_id": terminal_id,
        "instance_id": instance_id,
        "nonce": hello.payload.get("nonce"),
    }
    return Message.create(
        message_type=MessageType.HELLO_ACK,
        source=source,
        destination=destination,
        payload=payload,
        correlation_id=hello.request_id,
        request_id=hello.request_id,
    )


def negotiate_version(remote_version: Optional[str]) -> str:
    """Return negotiated protocol version or raise IncompatibleVersionError."""
    if not remote_version:
        raise IncompatibleVersionError("missing protocol_version")
    if remote_version not in SUPPORTED_PROTOCOLS:
        raise IncompatibleVersionError(
            f"unsupported protocol_version={remote_version}; supported={SUPPORTED_PROTOCOLS}"
        )
    return remote_version


def validate_hello_ack(ack: Message, hello: Message) -> dict:
    """Validate HELLO_ACK; returns payload on success."""
    if ack.message_type == MessageType.INCOMPATIBLE_VERSION:
        raise IncompatibleVersionError(
            f"peer rejected protocol: {ack.payload}"
        )
    if ack.message_type != MessageType.HELLO_ACK:
        raise HandshakeError(f"expected HELLO_ACK, got {ack.message_type}")
    if not ack.payload.get("accepted", False):
        raise HandshakeError(f"handshake rejected: {ack.payload}")
    remote_ver = ack.payload.get("protocol_version") or ack.protocol_version
    negotiate_version(remote_ver)
    # Optional nonce check
    if hello.payload.get("nonce") and ack.payload.get("nonce"):
        if ack.payload["nonce"] != hello.payload["nonce"]:
            raise HandshakeError("nonce mismatch")
    return dict(ack.payload)


class BridgeProtocol:
    """Thin helper object around protocol builders."""

    version = PROTOCOL_VERSION
    bridge_version = BRIDGE_VERSION

    def hello(self, **kw) -> Message:
        return build_hello(**kw)

    def hello_ack(self, hello: Message, **kw) -> Message:
        return build_hello_ack(hello, **kw)

    def validate_ack(self, ack: Message, hello: Message) -> dict:
        return validate_hello_ack(ack, hello)
