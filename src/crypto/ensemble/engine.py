"""Multi-model ensemble engine (inference only — no training, no orders)."""

from __future__ import annotations

import time
from collections.abc import Sequence

from crypto.ensemble.aggregate import EnsemblePrediction, aggregate_votes
from crypto.ensemble.weighting import WeightConfig
from crypto.exchanges.models import OHLCVBar
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.ml.base import BaseModel, ModelMetadata
from crypto.ml.governor import MLModelGovernor, MLSelection
from crypto.ml.features import compute_feature_row, select_features
from crypto.ml.labels import int_to_direction
from crypto.ml.prediction import ModelVote, Regime
from crypto.ml.regime import detect_regime


class EnsembleEngine:
    """Run multiple loaded models and aggregate votes."""

    def __init__(
        self,
        models: list[tuple[BaseModel, ModelMetadata]] | None = None,
        *,
        weight_config: WeightConfig | None = None,
        max_models: int = 4,
    ) -> None:
        self._max_models = max(1, max_models)
        self._models: list[tuple[BaseModel, ModelMetadata]] = list(models or [])[: self._max_models]
        self._weight_config = weight_config
        self._model_governor = MLModelGovernor()
        self._catalog: list[tuple[BaseModel, ModelMetadata]] = list(self._models)
        self._last_selection: MLSelection | None = None

    def add_model(self, model: BaseModel, meta: ModelMetadata) -> None:
        if len(self._catalog) >= 8:
            return
        self._catalog.append((model, meta))
        self._models = list(self._catalog[: self._max_models])

    def configure_governor(self, *, profile_name: str, state: object) -> MLSelection:
        """Apply hardware/governor selection without touching risk policy."""
        from crypto.governor.states import GovernorState

        if not isinstance(state, GovernorState):
            raise TypeError("state must be GovernorState")
        selection = self._model_governor.select(
            self._catalog, profile_name=profile_name, state=state
        )
        active = set(selection.active_algorithms)
        self._models = [item for item in self._catalog if item[1].algorithm.lower() in active]
        self._last_selection = selection
        return selection

    def observe_model(self, algorithm: str, *, latency_ms: float | None = None, success: bool = True) -> None:
        self._model_governor.observe(algorithm, latency_ms=latency_ms, success=success)

    @property
    def last_selection(self) -> MLSelection | None:
        return self._last_selection

    @property
    def loaded_algorithms(self) -> tuple[str, ...]:
        return tuple(meta.algorithm for _, meta in self._catalog)

    @property
    def model_count(self) -> int:
        return len(self._models)

    def predict(
        self,
        symbol: str,
        bars: Sequence[OHLCVBar],
        *,
        data_quality: DataQualityReport | None = None,
    ) -> EnsemblePrediction:
        quality = data_quality.quality if data_quality else DataQuality.UNKNOWN
        regime = detect_regime(bars) if bars else Regime.UNKNOWN
        ts = bars[-1].timestamp_ms if bars else 0

        if quality in (DataQuality.INVALID, DataQuality.STALE, DataQuality.UNKNOWN):
            return aggregate_votes(
                symbol,
                (),
                regime=regime,
                data_quality=quality,
                feature_timestamp_ms=ts,
            )

        if not self._models or not bars:
            return aggregate_votes(
                symbol,
                (),
                regime=regime,
                data_quality=quality,
                feature_timestamp_ms=ts,
            )

        votes: list[ModelVote] = []
        metrics: dict[str, dict[str, float]] = {}
        row = compute_feature_row(bars, len(bars) - 1)

        for model, meta in self._models:
            names, vals = select_features(
                row, meta.feature_names, max_features=len(meta.feature_names)
            )
            if len(names) != len(meta.feature_names):
                continue
            started = time.perf_counter()
            try:
                proba = model.predict_proba([list(vals)])[0]
            except Exception:
                self._model_governor.observe(
                    meta.algorithm, latency_ms=(time.perf_counter() - started) * 1000.0, success=False
                )
                continue
            self._model_governor.observe(
                meta.algorithm, latency_ms=(time.perf_counter() - started) * 1000.0, success=True
            )
            pred_cls = max(range(3), key=lambda i: proba[i])
            direction = int_to_direction(pred_cls)
            votes.append(
                ModelVote(
                    model_id=meta.model_id,
                    algorithm=meta.algorithm,
                    direction=direction,
                    probability_up=proba[2],
                    probability_down=proba[0],
                    probability_neutral=proba[1],
                )
            )
            if meta.metrics:
                metrics[meta.algorithm] = dict(meta.metrics)

        # volatility
        vol = 0.0
        if len(bars) >= 5:
            rets = []
            for i in range(len(bars) - 5, len(bars)):
                if bars[i - 1].close:
                    rets.append(abs((bars[i].close - bars[i - 1].close) / bars[i - 1].close))
            vol = sum(rets) / len(rets) if rets else 0.0

        return aggregate_votes(
            symbol,
            votes,
            regime=regime,
            data_quality=quality,
            feature_timestamp_ms=ts,
            volatility=vol,
            metrics=metrics or None,
            weight_config=self._weight_config,
        )
