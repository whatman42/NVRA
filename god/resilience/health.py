"""N.U.N.G. resilience health — no credentials, no orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ResilienceHealth:
    last_successful_cycle: Optional[str] = None
    last_failed_cycle: Optional[str] = None
    last_corrupted_cycle: Optional[str] = None
    last_snapshot: Optional[str] = None
    consecutive_failures: int = 0
    consecutive_stale_data: int = 0
    recovery_count: int = 0
    cycles_recorded: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_successful_cycle": self.last_successful_cycle,
            "last_failed_cycle": self.last_failed_cycle,
            "last_corrupted_cycle": self.last_corrupted_cycle,
            "last_snapshot": self.last_snapshot,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_stale_data": self.consecutive_stale_data,
            "recovery_count": self.recovery_count,
            "cycles_recorded": self.cycles_recorded,
        }
