"""Bridge errors — no trading intelligence."""

from __future__ import annotations


class BridgeError(Exception):
    """Base bridge error."""


class DiscoveryError(BridgeError):
    """Terminal discovery failure."""


class HandshakeError(BridgeError):
    """HELLO / HELLO_ACK failure."""


class IncompatibleVersionError(BridgeError):
    """Protocol version negotiation failed."""


class ReconciliationError(BridgeError):
    """State reconciliation failure."""


class InstallerError(BridgeError):
    """EA install / deploy failure (re-exported namespace)."""


class IntegrityError(BridgeError):
    """EA integrity verification failure."""


class HealingError(BridgeError):
    """Self-healing / recovery failure."""
