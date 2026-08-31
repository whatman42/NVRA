"""Foundational types and enumerations.

These are kept deliberately small and dependency-free so that every
later component can import them without pulling heavy libraries.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Final


class HardwareProfile(Enum):
    """Adaptive compute profile selected at startup and adjusted at runtime.

    Hardware profile controls only:
      - model count / tree count
      - feature complexity
      - inference frequency
      - worker count
      - cache size
      - parallelism

    Hardware profile MUST NEVER alter:
      - maximum risk
      - maximum drawdown
      - daily loss limit
      - kill-switch behaviour
      - exposure policy
      - any safety rule
    """

    ULTRA_LITE = auto()
    LITE = auto()
    BALANCED = auto()
    PERFORMANCE = auto()
    HEAVY = auto()
    EXTREME = auto()


class Severity(Enum):
    """Log / event severity levels used by the observability layer."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


# ---------------------------------------------------------------------------
# Secret handling
# ---------------------------------------------------------------------------

_REDACTED: Final[str] = "********"


class SecretStr:
    """Opaque string wrapper that never reveals its value via repr/str.

    Designed so that accidental logging, exception formatting, or
    interactive inspection cannot leak the underlying secret.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("SecretStr value must be a str")
        # Store under a private name; mypy understands instance attributes
        # assigned in __init__ even with __slots__.
        self._value: str = value

    def get_secret_value(self) -> str:
        """Return the raw secret. Call sites must treat the result as sensitive."""
        return self._value

    def __str__(self) -> str:
        return _REDACTED

    def __repr__(self) -> str:
        return f"SecretStr('{_REDACTED}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SecretStr):
            return NotImplemented
        # Constant-time comparison would be ideal for high-security contexts;
        # for Phase 1 we keep it simple and correct.
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        return len(self._value)


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

# Exchange identifiers are free-form strings so that Phase 2 can introduce
# concrete adapters without forcing storage-layer changes.
ExchangeId = str
AccountId = str
