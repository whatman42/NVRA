"""Adaptive computational budgets under governor state."""

from __future__ import annotations

from dataclasses import dataclass

from crypto.governor.states import GovernorState
from crypto.hardware.models import ResourceBudget


@dataclass(frozen=True, slots=True)
class AdaptiveBudget:
    """Current computational allowances — never risk limits."""

    state: GovernorState
    degradation_level: int
    workers: int
    max_ml_models: int
    max_universe: int
    max_candidates: int
    max_ml_candidates: int
    max_predictions_per_cycle: int
    max_opportunities: int
    prediction_cache_size: int
    feature_cache_size: int
    market_cache_size: int
    ohlcv_cache_size: int
    coalesce_interval_ms: int
    admit_training: bool
    admit_large_scan: bool
    ring2_enabled: bool
    ml_profile_name: str


def scale_budget(
    base: ResourceBudget,
    state: GovernorState,
    *,
    coalesce_degraded_ms: int = 250,
    coalesce_constrained_ms: int = 500,
) -> AdaptiveBudget:
    """Deterministic degradation ladder applied to Phase 8 ResourceBudget."""

    def clamp_int(v: int, lo: int = 1) -> int:
        return max(lo, int(v))

    if state is GovernorState.NORMAL:
        return AdaptiveBudget(
            state=state,
            degradation_level=0,
            workers=base.recommended_workers,
            max_ml_models=base.max_ml_models,
            max_universe=base.max_universe,
            max_candidates=base.max_candidates,
            max_ml_candidates=base.max_ml_candidates,
            max_predictions_per_cycle=base.max_predictions_per_cycle,
            max_opportunities=base.max_opportunities,
            prediction_cache_size=base.prediction_cache_size,
            feature_cache_size=base.feature_cache_size,
            market_cache_size=base.market_cache_size,
            ohlcv_cache_size=base.ohlcv_cache_size,
            coalesce_interval_ms=0,
            admit_training=True,
            admit_large_scan=True,
            ring2_enabled=True,
            ml_profile_name=base.ml_profile_name,
        )

    if state is GovernorState.DEGRADED:
        return AdaptiveBudget(
            state=state,
            degradation_level=2,
            workers=clamp_int(base.recommended_workers),
            max_ml_models=clamp_int(max(1, base.max_ml_models - 1)),
            max_universe=clamp_int(int(base.max_universe * 0.6)),
            max_candidates=clamp_int(int(base.max_candidates * 0.5)),
            max_ml_candidates=clamp_int(int(base.max_ml_candidates * 0.5)),
            max_predictions_per_cycle=clamp_int(int(base.max_predictions_per_cycle * 0.5)),
            max_opportunities=clamp_int(int(base.max_opportunities * 0.7)),
            prediction_cache_size=clamp_int(int(base.prediction_cache_size * 0.5)),
            feature_cache_size=clamp_int(int(base.feature_cache_size * 0.5)),
            market_cache_size=clamp_int(int(base.market_cache_size * 0.75)),
            ohlcv_cache_size=clamp_int(int(base.ohlcv_cache_size * 0.75)),
            coalesce_interval_ms=coalesce_degraded_ms,
            admit_training=False,
            admit_large_scan=True,
            ring2_enabled=False,
            ml_profile_name=_downgrade_ml(base.ml_profile_name, 1),
        )

    if state is GovernorState.RECOVERY:
        # Between CONSTRAINED and DEGRADED
        return AdaptiveBudget(
            state=state,
            degradation_level=3,
            workers=clamp_int(base.recommended_workers),
            max_ml_models=clamp_int(max(1, base.max_ml_models - 1)),
            max_universe=clamp_int(int(base.max_universe * 0.5)),
            max_candidates=clamp_int(int(base.max_candidates * 0.4)),
            max_ml_candidates=clamp_int(int(base.max_ml_candidates * 0.4)),
            max_predictions_per_cycle=clamp_int(int(base.max_predictions_per_cycle * 0.4)),
            max_opportunities=clamp_int(int(base.max_opportunities * 0.5)),
            prediction_cache_size=clamp_int(int(base.prediction_cache_size * 0.4)),
            feature_cache_size=clamp_int(int(base.feature_cache_size * 0.4)),
            market_cache_size=clamp_int(int(base.market_cache_size * 0.6)),
            ohlcv_cache_size=clamp_int(int(base.ohlcv_cache_size * 0.6)),
            coalesce_interval_ms=coalesce_degraded_ms,
            admit_training=False,
            admit_large_scan=False,
            ring2_enabled=False,
            ml_profile_name=_downgrade_ml(base.ml_profile_name, 1),
        )

    if state is GovernorState.CONSTRAINED:
        return AdaptiveBudget(
            state=state,
            degradation_level=4,
            workers=1,
            max_ml_models=1,
            max_universe=clamp_int(int(base.max_universe * 0.25)),
            max_candidates=clamp_int(int(base.max_candidates * 0.2)),
            max_ml_candidates=clamp_int(max(5, int(base.max_ml_candidates * 0.2))),
            max_predictions_per_cycle=clamp_int(max(3, int(base.max_predictions_per_cycle * 0.25))),
            max_opportunities=clamp_int(max(2, int(base.max_opportunities * 0.3))),
            prediction_cache_size=clamp_int(int(base.prediction_cache_size * 0.25)),
            feature_cache_size=clamp_int(int(base.feature_cache_size * 0.25)),
            market_cache_size=clamp_int(int(base.market_cache_size * 0.4)),
            ohlcv_cache_size=clamp_int(int(base.ohlcv_cache_size * 0.4)),
            coalesce_interval_ms=coalesce_constrained_ms,
            admit_training=False,
            admit_large_scan=False,
            ring2_enabled=False,
            ml_profile_name="ULTRA_LITE",
        )

    # CRITICAL
    return AdaptiveBudget(
        state=state,
        degradation_level=6,
        workers=1,
        max_ml_models=1,
        max_universe=clamp_int(int(base.max_universe * 0.1)),
        max_candidates=10,
        max_ml_candidates=3,
        max_predictions_per_cycle=1,
        max_opportunities=1,
        prediction_cache_size=8,
        feature_cache_size=8,
        market_cache_size=16,
        ohlcv_cache_size=16,
        coalesce_interval_ms=coalesce_constrained_ms,
        admit_training=False,
        admit_large_scan=False,
        ring2_enabled=False,
        ml_profile_name="ULTRA_LITE",
    )


def _downgrade_ml(name: str, steps: int) -> str:
    order = ["ULTRA_LITE", "LITE", "BALANCED", "PERFORMANCE", "EXTREME"]
    try:
        i = order.index(name)
    except ValueError:
        return "ULTRA_LITE"
    return order[max(0, i - steps)]
