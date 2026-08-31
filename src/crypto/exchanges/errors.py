"""Typed exchange errors.

CCXT exceptions are translated into these types so that core domain code
never depends on CCXT-specific exception classes.
"""

from __future__ import annotations


class ExchangeError(Exception):
    """Base class for all exchange-related errors."""

    def __init__(self, message: str, *, exchange_id: str | None = None) -> None:
        self.exchange_id = exchange_id
        super().__init__(message)


class AuthenticationError(ExchangeError):
    """API key/secret rejected or missing permissions for the requested action."""


class PermissionError(ExchangeError):
    """The credential lacks a required permission (e.g. read balance)."""


class RateLimitError(ExchangeError):
    """Exchange rate limit exceeded. Caller should back off."""


class NetworkError(ExchangeError):
    """Transient network / timeout failure."""


class MarketDataError(ExchangeError):
    """Invalid or unusable market data received from the exchange."""


class UnsupportedCapabilityError(ExchangeError):
    """The exchange (or current adapter mode) does not support this operation."""


class ExchangeUnavailableError(ExchangeError):
    """Exchange is down, under maintenance, or unreachable."""


class TradingDisabledError(ExchangeError):
    """Live order execution is disabled (Phase 2 invariant)."""


class CredentialMissingError(ExchangeError):
    """No credentials found in the CredentialStore for the requested account."""
