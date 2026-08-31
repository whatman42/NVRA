"""Market data freshness gate — blocks new proposals on stale data."""

from __future__ import annotations

import time

from crypto.governor.config import GovernorThresholds
from crypto.governor.states import DataFreshness


class MarketDataFreshnessGate:
    """Separate from RiskEngine: computational/data-quality gate only."""

    def __init__(self, thresholds: GovernorThresholds | None = None) -> None:
        self._t = thresholds or GovernorThresholds()

    def evaluate(self, last_update_ms: int | None, *, now_ms: int | None = None) -> DataFreshness:
        if last_update_ms is None:
            return DataFreshness.CRITICAL_STALE
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        age_s = max(0.0, (now - last_update_ms) / 1000.0)
        if age_s >= self._t.data_critical_stale_seconds:
            return DataFreshness.CRITICAL_STALE
        if age_s >= self._t.data_stale_seconds:
            return DataFreshness.STALE
        if age_s >= self._t.data_aging_seconds:
            return DataFreshness.AGING
        return DataFreshness.FRESH

    def allow_new_proposal(self, freshness: DataFreshness) -> bool:
        """STALE / CRITICAL_STALE block new strategy proposals."""
        return freshness in (DataFreshness.FRESH, DataFreshness.AGING)
