"""Rate-limit awareness for N.U.N.G. market data — no request storms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RateLimitInfo:
    limited: bool = False
    retry_after_seconds: Optional[float] = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "limited": self.limited,
            "retry_after_seconds": self.retry_after_seconds,
            "reason": self.reason,
        }


def parse_rate_limit_from_exception(exc: BaseException) -> RateLimitInfo:
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg or "throttle" in msg:
        # optional Retry-After: N
        retry_after = None
        for part in str(exc).split():
            if part.replace(".", "", 1).isdigit():
                try:
                    retry_after = float(part)
                    break
                except ValueError:
                    pass
        return RateLimitInfo(limited=True, retry_after_seconds=retry_after, reason="rate_limit")
    return RateLimitInfo(limited=False)


class RateLimitGuard:
    """Simple cooldown after rate-limit signal."""

    def __init__(self, *, now_fn=None) -> None:
        self._blocked_until: Optional[float] = None
        self._now = now_fn or (lambda: 0.0)
        self.last_info = RateLimitInfo()

    def allow(self) -> bool:
        if self._blocked_until is None:
            return True
        return float(self._now()) >= self._blocked_until

    def block(self, info: RateLimitInfo) -> None:
        self.last_info = info
        delay = info.retry_after_seconds if info.retry_after_seconds is not None else 1.0
        self._blocked_until = float(self._now()) + float(delay)

    def clear(self) -> None:
        self._blocked_until = None
        self.last_info = RateLimitInfo()
