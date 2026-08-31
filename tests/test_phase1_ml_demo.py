"""Phase 1 — ML persistence, ML-driven signal, sizing, DEMO execution, LIVE reject."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
from god.broker.mt5.demo_pipeline import DemoOnlyExecutionPipeline
from god.broker.mt5.fake import FakeMetaTrader5
from god.broker.mt5.models import MT5AccountMode
from god.market_decision import MarketDecisionEngine, Quote, SignalDirection
from god.ml import (
    Direction,
    MLPipeline,
    Prediction,
    PredictionStatus,
    evidence_from_prediction,
)
from god.ml.evidence import MLEvidence
from god.risk.sizing import PositionSizeRequest, compute_position_size


def _closes(n=200, seed=0, trend=0.0):
    rng = np.random.default_rng(seed)
    return (100 + np.cumsum(rng.normal(trend, 0.25, n))).astype(float).tolist()


def _force_champion(pipeline: MLPipeline) -> None:
    """Promote last model regardless of OOS threshold (test helper)."""
    if pipeline._last_model is None:
        return
    m = pipeline._last_model
    # ensure registered
    try:
        pipeline.registry.promote_champion(m.model_id, m.model_version)
    except KeyError:
        pipeline.registry.register_candidate(
            m,
            metrics=dict(m.metrics),
            calibrator=pipeline._calibrator,
            calibration=pipeline._calibration,
        )
        pipeline.registry.promote_champion(m.model_id, m.model_version)


def test_model_persist_reload_predict(tmp_path):
    root = tmp_path / "reg"
    p1 = MLPipeline(root, load_champion=False)
    closes = _closes(180, seed=7)
    out = p1.run(closes, regime="TRENDING", promote_champion=False)
    assert out.prediction is not None
    assert out.broker_orders_submitted == 0
    _force_champion(p1)
    pred_a = p1.predict(closes, regime="TRENDING")

    p2 = MLPipeline(root, load_champion=True)
    assert p2._last_model is not None
    pred_b = p2.predict(closes, regime="TRENDING")
    assert pred_a.direction == pred_b.direction
    assert abs(pred_a.probability - pred_b.probability) < 1e-9
    assert pred_a.model_id == pred_b.model_id


def test_ml_buy_path_drives_signal(tmp_path):
    eng = MarketDecisionEngine()
    eng.stream.on_message(sequence=1)
    pred = Prediction(
        model_id="m",
        model_version="1",
        timestamp="t",
        symbol="EURUSD",
        timeframe="H1",
        direction=Direction.UP,
        probability=0.72,
        confidence=0.6,
        features_version="feat-v1",
        status=PredictionStatus.VALID,
        regime="TRENDING",
    )
    ev = evidence_from_prediction(pred)
    assert ev.ml_gate_open
    q = Quote("EURUSD", time.time(), bid=1.1, ask=1.1001)
    closes = _closes(30, seed=1, trend=0.01)
    r = eng.run(quote=q, closes=closes, ml_evidence=ev, now=time.time())
    assert r.exchange_submissions == 0
    assert r.signal is not None
    assert r.signal.direction == SignalDirection.BUY
    assert "ml_up" in r.signal.reason


def test_ml_sell_path_drives_signal(tmp_path):
    eng = MarketDecisionEngine()
    eng.stream.on_message(sequence=1)
    pred = Prediction(
        model_id="m",
        model_version="1",
        timestamp="t",
        symbol="EURUSD",
        timeframe="H1",
        direction=Direction.DOWN,
        probability=0.7,
        confidence=0.55,
        features_version="feat-v1",
        status=PredictionStatus.VALID,
        regime="TRENDING",
    )
    ev = evidence_from_prediction(pred)
    q = Quote("EURUSD", time.time(), bid=1.1, ask=1.1001)
    closes = _closes(30, seed=2, trend=-0.01)
    r = eng.run(quote=q, closes=closes, ml_evidence=ev, now=time.time())
    assert r.exchange_submissions == 0
    assert r.signal is not None
    assert r.signal.direction == SignalDirection.SELL
    assert "ml_down" in r.signal.reason


def test_ml_hold_neutral(tmp_path):
    eng = MarketDecisionEngine()
    eng.stream.on_message(sequence=1)
    pred = Prediction(
        model_id="m",
        model_version="1",
        timestamp="t",
        symbol="EURUSD",
        timeframe="H1",
        direction=Direction.NEUTRAL,
        probability=0.5,
        confidence=0.1,
        features_version="feat-v1",
        status=PredictionStatus.VALID,
        regime="TRENDING",
    )
    ev = evidence_from_prediction(pred)
    assert not ev.ml_gate_open
    q = Quote("EURUSD", time.time(), bid=1.1, ask=1.1001)
    r = eng.run(quote=q, closes=_closes(30), ml_evidence=ev, now=time.time())
    assert r.action == "NO_TRADE" or "ml_gate_closed" in r.reasons
    assert r.exchange_submissions == 0


def test_ood_block(tmp_path):
    p = MLPipeline(tmp_path / "ood", load_champion=False)
    p.run(_closes(120), regime="TRENDING")
    pred = p.predict([float("nan")] * 30, regime="TRENDING")
    assert pred.status in (
        PredictionStatus.OUT_OF_DISTRIBUTION,
        PredictionStatus.INSUFFICIENT_DATA,
        PredictionStatus.MODEL_UNAVAILABLE,
    )
    assert pred.direction == Direction.NEUTRAL


def test_confidence_block(tmp_path):
    from god.ml.risk_gate import MLRiskGate

    gate = MLRiskGate(min_probability=0.55, min_confidence=0.5)
    pred = Prediction(
        model_id="m",
        model_version="1",
        timestamp="t",
        symbol="S",
        timeframe="H1",
        direction=Direction.UP,
        probability=0.56,
        confidence=0.2,
        features_version="feat-v1",
        status=PredictionStatus.VALID,
    )
    d = gate.evaluate(pred)
    assert not d.allowed
    assert d.reason == "confidence_below_min"


def test_risk_block_safe_mode():
    eng = MarketDecisionEngine(safe_mode=True)
    eng.stream.on_message(sequence=1)
    pred = Prediction(
        model_id="m",
        model_version="1",
        timestamp="t",
        symbol="EURUSD",
        timeframe="H1",
        direction=Direction.UP,
        probability=0.8,
        confidence=0.7,
        features_version="feat-v1",
        status=PredictionStatus.VALID,
        regime="TRENDING",
    )
    ev = evidence_from_prediction(pred)
    q = Quote("EURUSD", time.time(), bid=1.1, ask=1.1001)
    r = eng.run(quote=q, closes=_closes(30), ml_evidence=ev, now=time.time())
    assert r.action == "NO_TRADE"
    assert "SAFE_MODE" in r.reasons
    assert r.exchange_submissions == 0


def test_invalid_data_block():
    eng = MarketDecisionEngine()
    eng.stream.on_message(sequence=1)
    q = Quote("EURUSD", time.time(), bid=0.0, ask=1.1)
    r = eng.run(quote=q, closes=_closes(30), now=time.time())
    assert r.action == "NO_TRADE"
    assert r.exchange_submissions == 0


def test_position_sizing_ok():
    r = compute_position_size(
        PositionSizeRequest(
            equity=10_000,
            risk_pct=0.01,
            stop_distance=0.0020,
            tick_size=0.0001,
            tick_value=1.0,
            volume_min=0.01,
            volume_max=5.0,
            volume_step=0.01,
        )
    )
    assert r.ok
    assert r.volume >= 0.01
    assert r.raw_volume > 0


def test_position_sizing_fail_closed():
    r = compute_position_size(
        PositionSizeRequest(
            equity=0,
            risk_pct=0.01,
            stop_distance=0.002,
            tick_size=0.0001,
            tick_value=1.0,
        )
    )
    assert not r.ok
    assert r.volume == 0.0


def test_demo_execution_submit(tmp_path):
    fake = FakeMetaTrader5(trade_mode=0)
    adapter = MT5ExecutionAdapter(
        MT5ConnectionConfig(allow_live_account=False),
        mt5_module=fake,
    )
    ml = MLPipeline(tmp_path / "demo_ml", load_champion=False)
    pipe = DemoOnlyExecutionPipeline(adapter, ml_pipeline=ml, risk_pct=0.01)
    closes = _closes(160, seed=3)
    ml.run(closes, regime="TRENDING", promote_champion=False)
    _force_champion(ml)

    r0 = pipe.run(symbol="EURUSD", closes=closes, regime="TRENDING", submit_order=False)
    assert r0.account_mode == "DEMO"
    assert r0.exchange_submissions == 0
    assert r0.live_blocked is True

    r1 = pipe.run(symbol="EURUSD", closes=closes, regime="TRENDING", submit_order=True)
    assert r1.account_mode == "DEMO"
    assert r1.live_blocked is True
    assert r1.account_mode != "LIVE"


def test_live_execution_rejection():
    fake = FakeMetaTrader5(trade_mode=2)
    adapter = MT5ExecutionAdapter(
        MT5ConnectionConfig(allow_live_account=False),
        mt5_module=fake,
    )
    pipe = DemoOnlyExecutionPipeline(adapter)
    r = pipe.run(symbol="EURUSD", closes=_closes(50), submit_order=True)
    assert not r.ok
    assert r.exchange_submissions == 0
    assert r.live_blocked is True


def test_live_connect_blocked_by_adapter():
    fake = FakeMetaTrader5(trade_mode=2)
    adapter = MT5ExecutionAdapter(
        MT5ConnectionConfig(allow_live_account=False),
        mt5_module=fake,
    )
    ok = adapter.connect()
    assert ok is False or adapter.account_mode() != MT5AccountMode.LIVE


def test_restart_reload_behavior(tmp_path):
    root = tmp_path / "restart"
    closes = _closes(200, seed=9)
    a = MLPipeline(root, load_champion=False)
    a.run(closes, regime="TRENDING", promote_champion=False)
    _force_champion(a)
    pa = a.predict(closes, regime="TRENDING")

    b = MLPipeline(root, load_champion=True)
    assert b.reload_champion() is True
    pb = b.predict(closes, regime="TRENDING")
    assert pa.direction == pb.direction
    assert abs(pa.probability - pb.probability) < 1e-9


def test_production_execution_still_blocks_live():
    from god.production_execution.service import ProductionExecutionService
    from god.production_execution.models import ExecutionMode

    svc = ProductionExecutionService()
    req = svc.build_request(
        intent_id="i1",
        decision_id="d1",
        symbol="EURUSD",
        action="BUY",
        execution_mode=ExecutionMode.LIVE,
        environment="production",
    )
    result = svc.submit(req, grant=None)
    assert result.status.value in ("REJECTED", "UNAVAILABLE")
