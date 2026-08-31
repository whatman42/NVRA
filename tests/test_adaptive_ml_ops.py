"""Production-grade ops: telemetry, health, audit, recovery — Phase-3+.

LIVE remains blocked. No order_send.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from god.ml.audit import MLAuditTrail
from god.ml.health import HealthPolicy, ModelHealthMonitor
from god.ml.persist import save_trained_model
from god.ml.recovery import check_state_consistency, recover_champion
from god.ml.registry import ModelRecord, ModelRegistry
from god.ml.telemetry import MLTelemetry
from god.ml.train import train_baseline_classifier


def _xy(n: int = 80, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] + rng.normal(scale=0.3, size=n) > 0).astype(int)
    return X, y, tuple(f"f{i}" for i in range(4))


def test_telemetry_inference_and_summary():
    t = MLTelemetry(max_events=100)
    t.record_inference(
        model_id="m1",
        model_version="1",
        latency_ms=12.5,
        confidence=0.8,
        allow_trade=True,
        regime="TRENDING",
    )
    t.record_inference(
        model_id="m1",
        model_version="1",
        latency_ms=30.0,
        confidence=0.1,
        allow_trade=False,
        ood=True,
    )
    s = t.summary()
    assert s.inference_count == 2
    assert s.block_rate == pytest.approx(0.5)
    assert s.mean_latency_ms > 0
    assert len(t.recent_inferences()) == 2


def test_telemetry_training():
    t = MLTelemetry()
    t.record_training(
        model_id="m1",
        model_version="1",
        n_samples=100,
        duration_ms=500.0,
        oos_accuracy=0.62,
        status="ok",
        profile="BALANCED",
    )
    s = t.summary()
    assert s.train_count == 1
    assert t.recent_trainings()[0]["status"] == "ok"


def test_health_no_champion():
    mon = ModelHealthMonitor(registry=ModelRegistry(Path("/tmp/ml_empty_ops")))
    # fresh registry has no champion
    r = mon.evaluate()
    assert r.status == "UNKNOWN"
    assert r.prefer_no_trade


def test_health_degraded_high_block(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="h1", model_version="1")
    reg.register_candidate(model)
    reg.promote_champion("h1", "1")
    tel = MLTelemetry()
    for _ in range(10):
        tel.record_inference(
            model_id="h1",
            model_version="1",
            latency_ms=5.0,
            confidence=0.02,
            allow_trade=False,
        )
    mon = ModelHealthMonitor(registry=reg, telemetry=tel)
    report = mon.evaluate()
    assert report.status in ("DEGRADED", "CRITICAL")
    assert report.prefer_no_trade
    assert "high_block_rate" in report.reasons or "low_mean_confidence" in report.reasons


def test_audit_trail_memory_and_file(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    trail = MLAuditTrail(path=path)
    trail.record("promote", model_id="m1", model_version="1", outcome="allowed", detail={"acc": 0.6})
    trail.record("rollback", model_id="m1", model_version="1", outcome="success")
    recent = trail.recent()
    assert len(recent) == 2
    assert trail.by_type("promote")[0]["outcome"] == "allowed"
    assert path.is_file()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_recovery_restores_champion(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="r1", model_version="1")
    reg.register_candidate(model)
    reg.promote_champion("r1", "1")
    result, loaded = recover_champion(reg)
    assert result.success and result.status == "restored"
    assert loaded is not None
    assert loaded.model_id == "r1"


def test_recovery_corrupt_falls_back(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="old", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="new", model_version="2")
    reg.register_candidate(m1)
    reg.promote_champion("old", "1")
    reg.register_candidate(m2)
    reg.promote_champion("new", "2")
    # corrupt new champion artifact
    bundles = list(tmp_path.rglob("bundle.json"))
    assert bundles
    # find new's bundle and corrupt it
    for b in bundles:
        if "new@2" in str(b) or "new_2" in str(b).replace("-", "_"):
            b.write_text('{"model_id":"","model_version":""}', encoding="utf-8")
            break
    else:
        # corrupt any champion path
        bundles[0].write_text('{"model_id":"","model_version":""}', encoding="utf-8")
    result, loaded = recover_champion(reg, try_previous_on_corrupt=True)
    # either restored previous or failed closed — never raises
    assert result.status in ("restored", "corrupt", "no_champion")
    if result.success:
        assert loaded is not None


def test_state_consistency(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    c = check_state_consistency(reg)
    assert not c["consistent"]
    assert "no_champion" in c["issues"]


def test_ops_live_safety():
    from god.ml.adaptive import AdaptiveMLOrchestrator

    s = AdaptiveMLOrchestrator().safety_assertions()
    assert s["live_authorized"] is False
    assert s["broker_orders_submitted"] == 0
