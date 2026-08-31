"""Scanner candidate budgets and filter thresholds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScannerConfig:
    max_universe: int = 500
    max_candidates: int = 150
    max_ml_candidates: int = 40
    max_predictions_per_cycle: int = 20
    max_opportunities: int = 10

    # Cheap filters
    max_spread_pct: float = 1.0  # reject if (ask-bid)/mid > 1%
    min_quote_volume: float = 0.0  # 0 = disabled
    max_conversion_hops: int = 1

    # Cost awareness
    default_fee_pct: float = 0.1
    default_slippage_pct: float = 0.05

    # Opportunity
    min_opportunity_score: float = 0.15

    def validate(self) -> None:
        if self.max_ml_candidates > self.max_candidates:
            raise ValueError("max_ml_candidates cannot exceed max_candidates")
        if self.max_predictions_per_cycle > self.max_ml_candidates:
            raise ValueError("max_predictions_per_cycle cannot exceed max_ml_candidates")
