"""Phase 6E — deterministic bounded exponential backoff."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackoffPolicy:
    initial_delay: float = 0.01
    multiplier: float = 2.0
    max_delay: float = 1.0
    max_attempts: int = 3

    def delay_for_attempt(self, attempt: int) -> float:
        """attempt is 0-based. Deterministic, no jitter by default."""
        if attempt < 0:
            return 0.0
        d = self.initial_delay * (self.multiplier ** attempt)
        return min(d, self.max_delay)
