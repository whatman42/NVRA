"""Bounded retry / exponential backoff for N.U.N.G. market data transport."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


class FailureClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    PERMANENT = "PERMANENT"
    MALFORMED = "MALFORMED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    initial_backoff_seconds: float = 0.01
    max_backoff_seconds: float = 1.0
    multiplier: float = 2.0
    # tests use near-zero delays; no real sleep required when delay is 0

    def delay_for_attempt(self, attempt: int) -> float:
        """Deterministic exponential backoff. attempt is 0-based after first failure."""
        if attempt < 0:
            return 0.0
        delay = self.initial_backoff_seconds * (self.multiplier ** attempt)
        return min(delay, self.max_backoff_seconds)


def classify_exception(exc: BaseException) -> FailureClass:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timeout" in msg:
        return FailureClass.TIMEOUT
    if "rate" in msg or "429" in msg or "throttle" in msg:
        return FailureClass.RATE_LIMIT
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return FailureClass.TRANSIENT
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return FailureClass.MALFORMED
    if isinstance(exc, (PermissionError,)):
        return FailureClass.PERMANENT
    return FailureClass.UNKNOWN


def is_retryable(fc: FailureClass) -> bool:
    return fc in (
        FailureClass.TRANSIENT,
        FailureClass.TIMEOUT,
        FailureClass.RATE_LIMIT,
        FailureClass.UNKNOWN,
    )


def run_with_retry(
    fn: Callable[[], T],
    policy: Optional[RetryPolicy] = None,
    *,
    sleep_fn: Optional[Callable[[float], None]] = None,
) -> T:
    """
    Execute fn with bounded retries. Does not retry PERMANENT/MALFORMED.
    sleep_fn injectable (default: no-op for determinism in tests).
    """
    pol = policy or RetryPolicy()
    sleeper = sleep_fn or (lambda _d: None)
    last_exc: Optional[BaseException] = None
    attempts = 0
    while attempts <= pol.max_retries:
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            fc = classify_exception(exc)
            if not is_retryable(fc) or attempts >= pol.max_retries:
                raise
            sleeper(pol.delay_for_attempt(attempts))
            attempts += 1
    assert last_exc is not None
    raise last_exc
