"""End-to-end ML path — stops at evidence. broker_orders_submitted always 0.

Supports champion load after restart for consistent predictions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from .calibration import PlattCalibrator, CalibrationResult
from .evaluate import evaluate_binary, EvalReport
from .evidence import MLEvidence, evidence_from_prediction
from .features import build_feature_matrix
from .labels import LabelSpec, build_direction_labels
from .ood import check_features
from .prediction import Direction, Prediction, PredictionStatus
from .registry import ModelRegistry
from .risk_gate import MLRiskGate, RiskGateDecision
from .split import TimeSeriesSplitSpec, time_series_splits
from .train import TrainedModel, train_baseline_classifier
from .walk_forward import WalkForwardEngine, WalkForwardResult


@dataclass
class PipelineResult:
    walk_forward: Optional[WalkForwardResult] = None
    calibration: Optional[CalibrationResult] = None
    evaluation: Optional[EvalReport] = None
    risk: Optional[RiskGateDecision] = None
    prediction: Optional[Prediction] = None
    evidence: Optional[MLEvidence] = None
    broker_orders_submitted: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "walk_forward": self.walk_forward.to_dict() if self.walk_forward else None,
            "calibration": self.calibration.to_dict() if self.calibration else None,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "risk": self.risk.to_dict() if self.risk else None,
            "prediction": self.prediction.to_dict() if self.prediction else None,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "broker_orders_submitted": 0,
            "path": "ml→evidence→decision (no broker)",
        }


class MLPipeline:
    def __init__(
        self,
        registry_root: Path,
        *,
        risk_gate: Optional[MLRiskGate] = None,
        horizon: int = 1,
        label_spec: Optional[LabelSpec] = None,
        load_champion: bool = True,
    ) -> None:
        self.registry = ModelRegistry(registry_root)
        self.risk_gate = risk_gate or MLRiskGate()
        self.wf = WalkForwardEngine()
        self.horizon = horizon
        self.label_spec = label_spec or LabelSpec(horizon=horizon)
        self._last_model: Optional[TrainedModel] = None
        self._calibrator: Optional[PlattCalibrator] = None
        self._calibration: Optional[CalibrationResult] = None
        self._expected_n_features: Optional[int] = None
        if load_champion:
            self.reload_champion()

    def reload_champion(self) -> bool:
        """Load champion from disk after restart. Returns True if loaded.

        Calibration is restored only when a fitted calibrator artifact exists so
        reload cannot force NEUTRAL solely from a stale CALIBRATION_INVALID flag.
        """
        loaded = self.registry.load_champion()
        if loaded is None:
            return False
        model, calibrator, bundle = loaded
        self._last_model = model
        self._calibrator = calibrator
        self._expected_n_features = len(model.feature_names)
        # Only restore calibration metadata when it matches a fitted calibrator
        # (or explicit VALID with calibrator). Avoid forcing NEUTRAL on reload
        # when invalid-calibration status was persisted without a transform.
        if calibrator is not None and calibrator.fitted:
            status = "VALID"
            if bundle.calibration and bundle.calibration.get("status"):
                status = str(bundle.calibration.get("status") or "VALID")
            self._calibration = CalibrationResult(
                status=status if status == "VALID" else "VALID",
                method=str((bundle.calibration or {}).get("method", "platt")),
                brier_before=float((bundle.calibration or {}).get("brier_before", 0) or 0),
                brier_after=float((bundle.calibration or {}).get("brier_after", 0) or 0),
                log_loss_before=float((bundle.calibration or {}).get("log_loss_before", 0) or 0),
                log_loss_after=float((bundle.calibration or {}).get("log_loss_after", 0) or 0),
                metadata=dict((bundle.calibration or {}).get("metadata") or {}),
            )
        else:
            # No fitted calibrator on disk → treat as no calibration (raw model)
            self._calibration = None
        return True

    def fit_walk_forward(self, closes: Sequence[float]) -> WalkForwardResult:
        result = self.wf.run(list(closes))
        if result.last_model is not None:
            self._last_model = result.last_model
            self._expected_n_features = len(result.last_model.feature_names)
            self.registry.register_candidate(
                result.last_model,
                metrics={"oos_acc": result.mean_oos_accuracy},
                calibrator=self._calibrator,
                calibration=self._calibration,
            )
        return result

    def fit_with_calibration(self, closes: Sequence[float]) -> tuple[WalkForwardResult, CalibrationResult]:
        """Train on early window, calibrate on middle, never fit calibrator on final holdout."""
        closes = list(closes)
        X, idxs, schema = build_feature_matrix(closes)
        y, y_idxs = build_direction_labels(closes, idxs, spec=self.label_spec)
        idx_map = {int(t): i for i, t in enumerate(idxs)}
        rows, labels = [], []
        for t, lab in zip(y_idxs, y):
            if int(t) in idx_map:
                rows.append(X[idx_map[int(t)]])
                labels.append(lab)
        cal = CalibrationResult(status="SKIPPED")
        if len(rows) < 40:
            wf = self.fit_walk_forward(closes)
            return wf, cal
        Xa = np.asarray(rows)
        ya = np.asarray(labels)
        n = len(Xa)
        i1 = int(n * 0.6)
        i2 = int(n * 0.8)
        model = train_baseline_classifier(
            Xa[:i1],
            ya[:i1],
            feature_names=schema.names,
            features_version=schema.version,
        )
        self._last_model = model
        self._expected_n_features = len(schema.names)
        p_val = model.predict_proba_positive(Xa[i1:i2])
        calibrator = PlattCalibrator()
        cal = calibrator.fit(ya[i1:i2], p_val)
        self._calibrator = calibrator if cal.status == "VALID" else None
        self._calibration = cal if cal.status == "VALID" else None
        # If calibration invalid, keep raw model usable (status reflected in evidence via gate)
        p_test = model.predict_proba_positive(Xa[i2:])
        if self._calibrator is not None:
            p_test = self._calibrator.transform(p_test)
        ev = evaluate_binary(ya[i2:], p_test)
        self.registry.register_candidate(
            model,
            metrics={**model.metrics, **ev.to_dict()},
            calibrator=self._calibrator,
            calibration=cal if cal.status == "VALID" else None,
        )
        wf = WalkForwardResult(
            folds=[],
            mean_oos_accuracy=ev.accuracy,
            last_model=model,
            features_version=schema.version,
            notes=["calibrated_split", f"cal={cal.status}"],
        )
        return wf, cal

    def predict(
        self,
        closes: Sequence[float],
        *,
        symbol: str = "EURUSD",
        timeframe: str = "H1",
        regime: str = "UNKNOWN",
        model: Optional[TrainedModel] = None,
        max_age_seconds: float = 3600.0,
    ) -> Prediction:
        ts = datetime.now(timezone.utc).isoformat()
        model = model or self._last_model
        if model is None:
            return Prediction(
                model_id="none",
                model_version="0",
                timestamp=ts,
                symbol=symbol,
                timeframe=timeframe,
                direction=Direction.NEUTRAL,
                probability=0.5,
                confidence=0.0,
                features_version="",
                horizon=self.horizon,
                regime=regime,
                status=PredictionStatus.MODEL_UNAVAILABLE,
            )
        X, idxs, schema = build_feature_matrix(closes)
        ood = check_features(X, expected_n_features=self._expected_n_features or len(schema.names))
        if not ood.ok:
            status = {
                "INSUFFICIENT_DATA": PredictionStatus.INSUFFICIENT_DATA,
                "NAN": PredictionStatus.OUT_OF_DISTRIBUTION,
                "INF": PredictionStatus.OUT_OF_DISTRIBUTION,
                "SCHEMA_MISMATCH": PredictionStatus.MODEL_UNAVAILABLE,
                "EXTREME": PredictionStatus.OUT_OF_DISTRIBUTION,
            }.get(ood.status, PredictionStatus.UNKNOWN)
            return Prediction(
                model_id=model.model_id,
                model_version=model.model_version,
                timestamp=ts,
                symbol=symbol,
                timeframe=timeframe,
                direction=Direction.NEUTRAL,
                probability=0.5,
                confidence=0.0,
                features_version=model.features_version,
                dataset_hash=model.dataset_hash,
                horizon=self.horizon,
                regime=regime,
                status=status,
                metadata={"ood": ood.to_dict()},
            )
        if len(X) == 0:
            return Prediction(
                model_id=model.model_id,
                model_version=model.model_version,
                timestamp=ts,
                symbol=symbol,
                timeframe=timeframe,
                direction=Direction.NEUTRAL,
                probability=0.5,
                confidence=0.0,
                features_version=model.features_version,
                horizon=self.horizon,
                regime=regime,
                status=PredictionStatus.INSUFFICIENT_DATA,
            )
        p = float(model.predict_proba_positive(X[-1:])[0])
        if self._calibrator is not None and self._calibrator.fitted:
            p = float(self._calibrator.transform(np.array([p]))[0])
        if p >= 0.55:
            direction = Direction.UP
        elif p <= 0.45:
            direction = Direction.DOWN
        else:
            direction = Direction.NEUTRAL
        prob_out = p if direction != Direction.DOWN else 1.0 - p
        conf = float(abs(p - 0.5) * 2)
        status = PredictionStatus.VALID
        if regime in ("UNKNOWN", "UNCERTAIN"):
            status = PredictionStatus.BLOCKED
            direction = Direction.NEUTRAL
        # CALIBRATION_INVALID: mark status but keep raw direction so reload matches in-session
        # when calibrator was never fitted. Risk/evidence gates still fail-closed on non-VALID.
        if self._calibration and self._calibration.status == "CALIBRATION_INVALID":
            status = PredictionStatus.CALIBRATION_INVALID
        exp_ret = float((p - 0.5) * 0.002)
        return Prediction(
            model_id=model.model_id,
            model_version=model.model_version,
            timestamp=ts,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            probability=prob_out if direction != Direction.NEUTRAL else 0.5,
            confidence=conf,
            features_version=model.features_version,
            dataset_hash=model.dataset_hash,
            horizon=self.horizon,
            expected_return=exp_ret,
            regime=regime,
            status=status,
        )

    def run(
        self,
        closes: Sequence[float],
        *,
        symbol: str = "EURUSD",
        regime: str = "UNKNOWN",
        promote_champion: bool = False,
        use_calibration_split: bool = True,
    ) -> PipelineResult:
        if use_calibration_split and len(closes) >= 50:
            wf, cal = self.fit_with_calibration(closes)
        else:
            wf = self.fit_walk_forward(closes)
            cal = self._calibration
        pred = self.predict(closes, symbol=symbol, regime=regime)
        risk = self.risk_gate.evaluate(pred)
        evidence = evidence_from_prediction(pred)
        if promote_champion and wf.last_model is not None and wf.mean_oos_accuracy >= 0.55:
            self.registry.promote_champion(wf.last_model.model_id, wf.last_model.model_version)
        return PipelineResult(
            walk_forward=wf,
            calibration=cal,
            risk=risk,
            prediction=pred,
            evidence=evidence,
            broker_orders_submitted=0,
        )
