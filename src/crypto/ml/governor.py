"""Adaptive ML model selection based on resource budget and model health.

This module is computational control only. It never changes risk limits or
trading authorization. Model selection is deterministic, bounded, and
auditable so a high-end machine does not automatically activate every model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from crypto.governor.states import GovernorState
from crypto.ml.base import ModelMetadata


@dataclass(frozen=True, slots=True)
class ModelHealth:
    """Runtime health for one model."""

    algorithm: str
    latency_ms_ewma: float = 0.0
    error_rate: float = 0.0
    samples: int = 0

    @property
    def healthy(self) -> bool:
        return self.error_rate < 0.20 and self.latency_ms_ewma < 2000.0


@dataclass(frozen=True, slots=True)
class MLSelection:
    """Auditable selection decision."""

    active_algorithms: tuple[str, ...]
    considered_algorithms: tuple[str, ...]
    rejected_algorithms: tuple[str, ...]
    reason: str


class MLModelGovernor:
    """Selects a bounded subset of loaded models.

    Hardware determines the ceiling; model quality/health determines which
    models deserve a slot. Fallback is only selected when no optional model
    is available. The governor cannot authorize orders.
    """

    _PROFILE_SLOTS = {
        "ULTRA_LITE": 1,
        "LITE": 1,
        "BALANCED": 2,
        "PERFORMANCE": 3,
        "EXTREME": 4,
    }
    _STATE_SLOTS = {
        GovernorState.NORMAL: 1.0,
        GovernorState.RECOVERY: 0.75,
        GovernorState.DEGRADED: 0.60,
        GovernorState.CONSTRAINED: 0.25,
        GovernorState.CRITICAL: 0.25,
    }
    _MIN_SCORE = 0.34

    def __init__(self) -> None:
        self._health: dict[str, ModelHealth] = {}
        self._last: MLSelection | None = None

    def observe(
        self,
        algorithm: str,
        *,
        latency_ms: float | None = None,
        success: bool = True,
    ) -> None:
        """Update bounded runtime health using EWMA."""
        key = algorithm.lower()
        old = self._health.get(key, ModelHealth(key))
        n = min(old.samples + 1, 100_000)
        alpha = 0.20
        latency = old.latency_ms_ewma
        if latency_ms is not None:
            value = max(0.0, float(latency_ms))
            latency = value if old.samples == 0 else (1.0 - alpha) * latency + alpha * value
        err = 0.0 if success else 1.0
        error_rate = err if old.samples == 0 else (1.0 - alpha) * old.error_rate + alpha * err
        self._health[key] = ModelHealth(key, latency, error_rate, n)

    def select(
        self,
        models: Iterable[tuple[object, ModelMetadata]],
        *,
        profile_name: str,
        state: GovernorState = GovernorState.NORMAL,
    ) -> MLSelection:
        loaded: dict[str, tuple[object, ModelMetadata]] = {}
        for model, meta in models:
            algo = meta.algorithm.lower()
            # Prefer the newest/last loaded artifact for duplicate algorithms.
            loaded[algo] = (model, meta)

        considered = tuple(sorted(loaded))
        if not loaded:
            result = MLSelection((), (), (), "no models loaded")
            self._last = result
            return result

        ceiling = self._PROFILE_SLOTS.get(profile_name, 1)
        state_factor = self._STATE_SLOTS.get(state, 0.25)
        slots = max(1, min(ceiling, int(ceiling * state_factor)))

        scored: list[tuple[float, str]] = []
        for algo, (_, meta) in loaded.items():
            score = self._quality_score(meta)
            health = self._health.get(algo)
            if health:
                score *= max(0.25, 1.0 - min(0.75, health.error_rate))
                if health.latency_ms_ewma > 500:
                    score *= max(0.35, 500.0 / health.latency_ms_ewma)
            # Fallback is a safety net, not an ensemble peer when real models exist.
            if algo == "fallback" and len(loaded) > 1:
                score *= 0.25
            if score >= self._MIN_SCORE or algo == "fallback":
                scored.append((score, algo))

        scored.sort(key=lambda x: (-x[0], x[1]))
        active = [algo for _, algo in scored[:slots]]

        if not active:
            # Deterministic safety fallback: use the best available artifact.
            active = [max(loaded, key=lambda a: self._quality_score(loaded[a][1]))]

        rejected = tuple(algo for algo in considered if algo not in active)
        reason = (
            f"profile={profile_name} state={state.name} slots={slots}/{ceiling}; "
            f"active={','.join(active)}"
        )
        result = MLSelection(tuple(active), considered, rejected, reason)
        self._last = result
        return result

    @staticmethod
    def _quality_score(meta: ModelMetadata) -> float:
        """Prefer test accuracy, then validation accuracy, with conservative defaults."""
        metrics = meta.metrics or {}
        value = metrics.get("test_accuracy")
        if value is None:
            value = metrics.get("accuracy")
        if value is None:
            return 0.34
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.34

    @property
    def last_selection(self) -> MLSelection | None:
        return self._last

    def health_snapshot(self) -> dict[str, ModelHealth]:
        return dict(self._health)
