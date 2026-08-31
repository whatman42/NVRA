"""IPC errors — no trading intelligence."""

from __future__ import annotations


class IPCError(Exception):
    """Base IPC error."""


class TimeoutError(IPCError):
    """Request or receive timed out."""


class ConnectionError(IPCError):
    """Connect / disconnect / send failures."""


class ProtocolError(IPCError):
    """Malformed message or version mismatch."""
