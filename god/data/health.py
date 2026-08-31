"""Source health model for N.U.N.G. market data — fail-closed."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SourceHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    CORRUPTED = "CORRUPTED"
    UNKNOWN = "UNKNOWN"


@dataclass
class SourceHealth:
    state: SourceHealthState = SourceHealthState.UNKNOWN
    reason: str = ""
    source_id: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "reason": self.reason,
            "source_id": self.source_id,
            "metadata": dict(self.metadata),
        }

    @property
    def is_usable(self) -> bool:
        return self.state in (SourceHealthState.HEALTHY, SourceHealthState.DEGRADED)
