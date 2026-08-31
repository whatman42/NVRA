"""IPCTransport protocol — environment-agnostic messaging contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional

from .models import Message, ConnectionState


@runtime_checkable
class IPCTransport(Protocol):
    """Abstract transport used by BridgeManager.

    Implementations: TcpTransport (Phase 3B-A), future NamedPipeTransport.
    """

    @property
    def name(self) -> str:
        ...

    @property
    def state(self) -> ConnectionState:
        ...

    def connect(self, timeout: float = 5.0) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def send(self, message: Message) -> None:
        ...

    def receive(self, timeout: float = 5.0) -> Optional[Message]:
        """Return next message or None on timeout (non-raising)."""
        ...

    def request(self, message: Message, timeout: float = 5.0) -> Message:
        """Send and wait for a response with matching request_id / correlation."""
        ...

    def health(self) -> dict:
        """Lightweight transport health snapshot."""
        ...
