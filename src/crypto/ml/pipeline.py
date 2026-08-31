"""Training and live inference — strictly separated."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from crypto.exchanges.models import OHLCVBar
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.ml.artifacts import data_hash, new_metadata, save_artifact
from crypto.ml.backends import available_algorithms, create_model
from crypto.ml.base import BaseModel, ModelMetadata
from crypto.ml.features import (
    FEATURE_NAMES,
    build_feature_matrix,
    compute_feature_row,
    select_features,
)
from crypto.ml.labels import (
    LabelConfig,
    build_labels,
    chronological_split,
    direction_to_int,
    int_to_direction,
)
from crypto.ml.prediction import Direction, ModelVote, Prediction
from crypto.ml.profiles import DEFAULT_PROFILE, MLProfile, ResourceLimits, limits_for
from crypto.ml.regime import detect_regime


@dataclass(frozen=True, slots=True)
class TrainResult:
    model: BaseModel
    metadata: ModelMetadata
    metrics: dict[str, float]


class MLPipeline:
    """Fit is explicit. Live path only calls predict_* — never fit."""

    def __init__(
        self,
        profile: MLProfile = DEFAULT_PROFILE,
        label_config: LabelConfig | None = None,
    ) -> None:
        self.profile = profile
        self.limits: ResourceLimits = limits_for(profile)
        self.label_config = label_config or LabelConfig()
        self._model: BaseModel | None = None
        self._meta: ModelMetadata | None = None

    @property
    def is_trained(self) -> bool:
        return self._model is not None and self._meta is not None

    def select_algorithm(self) -> str:
        avail = set(available_algorithms())
        for algo in self.limits.algorithms:
            if algo in avail:
                return algo
        return "fallback"

    def train(self, bars: Sequence[OHLCVBar]) -> TrainResult:
        """Explicit training only — never called from live tick path."""
        rows, indices = build_feature_matrix(
            bars,
            min_history=20,
            max_rows=self.limits.max_training_rows,
        )
        labels = build_labels(bars, indices, self.label_config)
        # Drop rows without labels (tail horizon)
        paired = [
            (r, direction_to_int(lab))
            for r, lab in zip(rows, labels, strict=True)
            if lab is not None
        ]
        if len(paired) < 30:
            raise ValueError(f"insufficient labeled rows: {len(paired)}")

        feat_names = FEATURE_NAMES[: self.limits.max_features]
        x_all = [
            list(select_features(r, feat_names, self.limits.max_features)[1]) for r, _ in paired
        ]
        y_all = [y for _, y in paired]

        tr, va, te = chronological_split(len(x_all))
        x_train = [x_all[i] for i in tr]
        y_train = [y_all[i] for i in tr]
        x_val = [x_all[i] for i in va] if len(va) else x_train[-10:]
        y_val = [y_all[i] for i in va] if len(va) else y_train[-10:]

        algo = self.select_algorithm()
        model = create_model(algo, self.limits)
        model.fit(x_train, y_train, feature_names=feat_names)

        metrics = _eval_metrics(model, x_val, y_val)
        # light test metrics if test split non-empty
        if len(te):
            x_te = [x_all[i] for i in te]
            y_te = [y_all[i] for i in te]
            test_m = _eval_metrics(model, x_te, y_te)
            metrics.update({f"test_{k}": v for k, v in test_m.items()})

        meta = new_metadata(
            algorithm=algo,
            feature_names=tuple(feat_names),
            training_rows=len(x_train),
            training_data_hash=data_hash([tuple(r) for r in x_train]),
            hyperparameters={
                "max_trees": self.limits.max_trees,
                "max_depth": self.limits.max_depth,
                "max_threads": self.limits.max_threads,
            },
            metrics=metrics,
            profile=self.profile.name,
            horizon=self.label_config.horizon_bars,
        )
        self._model = model
        self._meta = meta
        return TrainResult(model=model, metadata=meta, metrics=metrics)

    def load(self, model: BaseModel, meta: ModelMetadata) -> None:
        if meta.feature_schema_version != "v1":
            raise ValueError("incompatible feature schema")
        self._model = model
        self._meta = meta

    def predict(
        self,
        symbol: str,
        bars: Sequence[OHLCVBar],
        *,
        data_quality: DataQualityReport | None = None,
    ) -> Prediction:
        """Live inference only — does not train."""
        if self._model is None or self._meta is None:
            raise RuntimeError("model not loaded/trained")
        quality = data_quality.quality if data_quality else DataQuality.UNKNOWN
        if quality in (DataQuality.INVALID, DataQuality.STALE, DataQuality.UNKNOWN):
            return Prediction(
                symbol=symbol,
                direction=Direction.NEUTRAL,
                probability=0.0,
                confidence=0.0,
                confidence_calibrated=False,
                expected_return=0.0,
                volatility_estimate=0.0,
                regime=detect_regime(bars),
                model_id=self._meta.model_id,
                algorithm=self._meta.algorithm,
                feature_timestamp_ms=bars[-1].timestamp_ms if bars else 0,
                generated_at_ms=int(time.time() * 1000),
                data_quality=quality,
                horizon_bars=self._meta.label_horizon_bars,
            )

        row = compute_feature_row(bars, len(bars) - 1)
        names, vals = select_features(row, self._meta.feature_names, self.limits.max_features)
        expected_names = tuple(self._meta.feature_names[: len(names)])
        if names != expected_names:
            raise ValueError("feature schema mismatch at inference")

        proba = self._model.predict_proba([list(vals)])[0]
        pred_cls = max(range(3), key=lambda i: proba[i])
        direction = int_to_direction(pred_cls)
        probability = proba[pred_cls]
        # Confidence: gap between top and second (uncalibrated)
        ranked_p = sorted(proba, reverse=True)
        confidence = float(ranked_p[0] - ranked_p[1]) if len(ranked_p) > 1 else float(ranked_p[0])
        expected_ret = (proba[2] - proba[0]) * 0.01  # coarse expected return scale
        # vol from recent returns
        vol = 0.0
        if len(bars) >= 5:
            rets = []
            for i in range(len(bars) - 5, len(bars)):
                if bars[i - 1].close:
                    rets.append(abs((bars[i].close - bars[i - 1].close) / bars[i - 1].close))
            vol = sum(rets) / len(rets) if rets else 0.0

        vote = ModelVote(
            model_id=self._meta.model_id,
            algorithm=self._meta.algorithm,
            direction=direction,
            probability_up=proba[2],
            probability_down=proba[0],
            probability_neutral=proba[1],
        )
        return Prediction(
            symbol=symbol,
            direction=direction,
            probability=float(probability),
            confidence=max(0.0, min(1.0, confidence)),
            confidence_calibrated=False,
            expected_return=float(expected_ret),
            volatility_estimate=float(vol),
            regime=detect_regime(bars),
            model_id=self._meta.model_id,
            algorithm=self._meta.algorithm,
            feature_timestamp_ms=row.timestamp_ms,
            generated_at_ms=int(time.time() * 1000),
            data_quality=quality,
            votes=(vote,),
            horizon_bars=self._meta.label_horizon_bars,
        )

    def save(self, path: str) -> None:
        if self._model is None or self._meta is None:
            raise RuntimeError("nothing to save")
        save_artifact(path, self._model, self._meta)


def _eval_metrics(
    model: BaseModel, x: Sequence[Sequence[float]], y: Sequence[int]
) -> dict[str, float]:
    if not x:
        return {"accuracy": 0.0, "n": 0.0}
    preds = model.predict(x)
    correct = sum(1 for a, b in zip(preds, y, strict=True) if a == b)
    acc = correct / len(y)
    # per-class recall rough
    return {"accuracy": acc, "n": float(len(y))}
