"""IPC transport layer — protocol-agnostic messaging.

Phase 3B-A: TCP localhost transport (testable on Linux CI).
Future: NamedPipeTransport (Windows) without changing AgentCore.
"""

from .models import Message, MessageType, ConnectionState
from .protocols import IPCTransport
from .tcp import TcpTransport
from .errors import IPCError, TimeoutError, ConnectionError, ProtocolError

__all__ = [
    "Message",
    "MessageType",
    "ConnectionState",
    "IPCTransport",
    "TcpTransport",
    "IPCError",
    "TimeoutError",
    "ConnectionError",
    "ProtocolError",
]
