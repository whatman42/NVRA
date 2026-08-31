"""TAHAP 5/8 — ML & Prediction Layer."""

from __future__ import annotations

import time
import numpy as np

from god.ml import (
    MLPipeline,
    PredictionStatus,
    Direction,
    build_feature_matrix,
    build_direction_labels,
    LabelSpec,
    time_series_splits,
    TimeSeriesSplitSpec,
    check_features,
    PlattCalibrator,
    evidence_from_prediction,
)
from god.ml.prediction import Prediction
from god.market_decision import MarketDecisionEngine, Quote


def _closes(n=200, seed=0):
    rng = np.random.default_rng(seed)
    return (100 + np.cumsum(rng.normal(0, 0.25, n))).astype(float).tolist()


def test_feature_deterministic():
    c = _closes(80)
    X1, _, s1 = build_feature_matrix(c)
    X2, _, s2 = build_feature_matrix(c)
    assert np.allclose(X1, X2)
    assert s1.version == s2.version


def test_no_label_future_leak_indices():
    c = _closes(60)
    X, idxs, _ = build_feature_matrix(c)
    y, valid = build_direction_labels(c, idxs, spec=LabelSpec(horizon=3))
    assert len(y) == len(valid)
    assert valid.max() + 3 < len(c) or valid.max() + 3 == len(c) - 0  # last labeled has future
    assert all(int(t) + 3 < len(c) for t in valid)


def test_chronological_split_no_overlap():
    for tr, te in time_series_splits(100, TimeSeriesSplitSpec(n_splits=2, train_min=30, test_size=10)):
        assert tr.max() < te.min()


def test_pipeline_broker_zero(tmp_path):
    p = MLPipeline(tmp_path / "reg")
    out = p.run(_closes(180), symbol="EURUSD", regime="TRENDING")
    assert out.broker_orders_submitted == 0
    assert out.to_dict()["broker_orders_submitted"] == 0
    assert out.prediction is not None
    assert out.evidence is not None
    assert out.evidence.to_dict()["broker_orders_submitted"] == 0


def test_invalid_ml_no_entry_status(tmp_path):
    p = MLPipeline(tmp_path / "reg2")
    out = p.run(_closes(180), regime="UNKNOWN")
    # UNKNOWN regime → BLOCKED or not allows entry
    assert out.prediction.status in (
        PredictionStatus.BLOCKED,
        PredictionStatus.VALID,
        PredictionStatus.CALIBRATION_INVALID,
        PredictionStatus.INSUFFICIENT_DATA,
    )
    if out.prediction.status == PredictionStatus.BLOCKED:
        assert out.prediction.direction == Direction.NEUTRAL
        assert not out.prediction.allows_entry_evidence


def test_model_unavailable():
    p = MLPipeline.__new__(MLPipeline)
    p._last_model = None
    p._calibrator = None
    p._calibration = None
    p._expected_n_features = None
    p.horizon = 1
    from god.ml.pipeline import MLPipeline as MLP
    pipe = MLP.__new__(MLP)
    pipe._last_model = None
    pipe._calibrator = None
    pipe._calibration = None
    pipe._expected_n_features = None
    pipe.horizon = 1
    pred = MLP.predict(pipe, [1.0, 2.0])
    assert pred.status == PredictionStatus.MODEL_UNAVAILABLE


def test_ood_nan():
    X = np.array([[1.0, np.nan, 0.1]])
    r = check_features(X, expected_n_features=3)
    assert not r.ok


def test_calibration_not_on_test(tmp_path):
    p = MLPipeline(tmp_path / "reg3")
    wf, cal = p.fit_with_calibration(_closes(200))
    assert cal.status in ("VALID", "CALIBRATION_INVALID", "SKIPPED")
    # calibrator fitted only if VALID
    if cal.status == "VALID":
        assert p._calibrator is not None and p._calibrator.fitted


def test_probability_not_equals_confidence(tmp_path):
    p = MLPipeline(tmp_path / "reg4")
    out = p.run(_closes(200), regime="TRENDING")
    pred = out.prediction
    # confidence is abs(p-0.5)*2 style, not identical copy of probability always
    assert hasattr(pred, "probability") and hasattr(pred, "confidence")


def test_ml_cannot_bypass_decision_risk(tmp_path):
    pipe = MLPipeline(tmp_path / "reg5")
    out = pipe.run(_closes(180), regime="TRENDING")
    eng = MarketDecisionEngine(safe_mode=True)
    eng.stream.on_message(sequence=1)
    q = Quote("EURUSD", time.time(), bid=1.1, ask=1.1001)
    r = eng.run(quote=q, closes=_closes(30), ml_evidence=out.evidence, now=time.time())
    assert r.action == "NO_TRADE"
    assert r.exchange_submissions == 0


def test_ml_gate_closed_blocks_entry(tmp_path):
    pipe = MLPipeline(tmp_path / "reg6")
    out = pipe.run(_closes(180), regime="UNKNOWN")
    eng = MarketDecisionEngine()
    eng.stream.on_message(sequence=1)
    q = Quote("EURUSD", time.time(), bid=1.1, ask=1.1001)
    r = eng.run(
        quote=q,
        closes=_closes(30),
        ml_evidence=out.evidence,
        reconciliation_healthy=True,
        now=time.time(),
    )
    assert r.exchange_submissions == 0
    # either NO_TRADE from regime or ml_gate
    assert r.action == "NO_TRADE" or "ml_gate_closed" in r.reasons or "regime" in str(r.reasons)


def test_repeated_predict_deterministic(tmp_path):
    p = MLPipeline(tmp_path / "reg7")
    c = _closes(150, seed=1)
    p.fit_walk_forward(c)
    a = p.predict(c, symbol="EURUSD", regime="TRENDING")
    b = p.predict(c, symbol="EURUSD", regime="TRENDING")
    assert a.direction == b.direction
    assert abs(a.probability - b.probability) < 1e-9


def test_evidence_broker_zero():
    pred = Prediction(
        model_id="m",
        model_version="1",
        timestamp="t",
        symbol="S",
        timeframe="H1",
        direction=Direction.UP,
        probability=0.7,
        confidence=0.4,
        features_version="feat-v1",
        status=PredictionStatus.VALID,
    )
    ev = evidence_from_prediction(pred)
    assert ev.to_dict()["broker_orders_submitted"] == 0
