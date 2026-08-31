"""Phase-3 Adaptive ML — dataset, scheduler, rollback, uncertainty, calibration, safety."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from god.ml.calibration import IsotonicCalibrator, PlattCalibrator, select_and_fit_calibrator
from god.ml.dataset import (
    build_dataset_snapshot,
    compute_matrix_checksum,
    detect_leakage,
    validate_snapshot,
)
from god.ml.evaluate import evaluate_binary
from god.ml.hardware import HardwareSnapshot, ResourceGovernor, build_resource_limits, select_profile
from god.ml.persist import load_trained_model_safe, save_trained_model, validate_artifact_bundle
from god.ml.promotion import evaluate_promotion, evaluate_rollback, try_rollback
from god.ml.registry import ModelRecord, ModelRegistry
from god.ml.scheduler import SchedulerConfig, TrainingScheduler
from god.ml.train import train_baseline_classifier
from god.ml.uncertainty import evaluate_uncertainty, prediction_confidence


def _snap(ram: int = 16384, **kw) -> HardwareSnapshot:
    d = dict(
        cpu_cores=4,
        cpu_threads=8,
        available_ram_mb=ram // 2,
        gpu_available=False,
        vram_mb=0,
        available_disk_mb=50_000,
        cpu_percent=10.0,
        memory_percent=40.0,
        platform="Linux",
        architecture="x86_64",
        notes=("t",),
    )
    d.update(kw)
    return HardwareSnapshot(total_ram_mb=ram, **d)


def _xy(n: int = 80, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] + rng.normal(scale=0.3, size=n) > 0).astype(int)
    return X, y, tuple(f"f{i}" for i in range(4))


def test_dataset_ok():
    X, y, _ = _xy(80)
    s = build_dataset_snapshot(X, y)
    assert s.valid and s.checksum
    assert validate_snapshot(s)[0]


def test_dataset_insufficient_fail_closed():
    s = build_dataset_snapshot(np.ones((5, 2)), np.array([0, 1, 0, 1, 0]), min_samples=30)
    assert not s.valid


def test_leakage_clean_and_overlap():
    ok, _ = detect_leakage(np.arange(50), np.arange(52, 72), embargo=1)
    assert ok
    bad, reason = detect_leakage(np.arange(50), np.arange(40, 60), embargo=1)
    assert not bad and "overlap" in reason


def test_scheduler_initial():
    gov = ResourceGovernor()
    gov._limits = build_resource_limits(_snap(), select_profile(_snap()))
    s = TrainingScheduler(governor=gov, config=SchedulerConfig(min_samples_absolute=40))
    d = s.evaluate(current_samples=50, now_ts=1.0)
    assert d.eligible and d.reason == "initial_train"


def test_scheduler_performance_degradation():
    gov = ResourceGovernor()
    gov._limits = build_resource_limits(_snap(), select_profile(_snap()))
    s = TrainingScheduler(
        governor=gov,
        config=SchedulerConfig(min_new_samples=10, min_hours_between=0.0, performance_drop_threshold=0.05),
    )
    s.mark_trained(100, ts=1.0, oos_accuracy=0.70, regime="TRENDING")
    d = s.evaluate(current_samples=200, now_ts=100000.0, current_oos_accuracy=0.55)
    assert d.eligible and d.reason == "performance_degradation"


def test_scheduler_regime_change():
    gov = ResourceGovernor()
    gov._limits = build_resource_limits(_snap(), select_profile(_snap()))
    s = TrainingScheduler(
        governor=gov,
        config=SchedulerConfig(min_new_samples=10, min_hours_between=0.0),
    )
    s.mark_trained(100, ts=1.0, oos_accuracy=0.60, regime="TRENDING")
    d = s.evaluate(current_samples=200, now_ts=100000.0, current_regime="RANGING", current_oos_accuracy=0.59)
    assert d.eligible and d.reason == "regime_change"


def test_hardware_alone_cannot_promote():
    rec = ModelRecord(
        model_id="m1",
        model_version="v1",
        status="challenger",
        features_version="fs",
        dataset_hash="h",
        oos_metrics={"accuracy": 0.9, "brier": 0.1, "n": 100},
    )
    gate = evaluate_promotion(rec, hardware_only=True)
    assert not gate.allowed and "hardware" in gate.reason


def test_rollback_restores_previous(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    r1 = ModelRecord(
        model_id="old",
        model_version="1",
        status="retired",
        features_version="fs",
        dataset_hash="h1",
        oos_metrics={"accuracy": 0.6},
        saved_at="2020-01-01T00:00:00",
    )
    r2 = ModelRecord(
        model_id="new",
        model_version="2",
        status="champion",
        features_version="fs",
        dataset_hash="h2",
        oos_metrics={"accuracy": 0.4},
        saved_at="2020-02-01T00:00:00",
    )
    reg._records = [r1, r2]
    reg._save()
    result = try_rollback(reg, performance_collapse=True)
    assert result.success and result.restored_id == "old"
    assert reg.champion().model_id == "old"


def test_rollback_no_trigger():
    assert not evaluate_rollback(champion=None, previous=None).success


def test_uncertainty():
    assert evaluate_uncertainty(0.9).allow_trade
    assert not evaluate_uncertainty(0.51, min_confidence=0.2).allow_trade
    assert prediction_confidence(0.5) == pytest.approx(0.0)


def test_f1():
    r = evaluate_binary(np.array([0, 1, 1, 0, 1]), np.array([0.1, 0.9, 0.8, 0.2, 0.7]))
    assert r.f1 > 0


def test_platt_and_select_calibrator():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, size=40)
    p = np.clip(y.astype(float) * 0.6 + 0.2 + rng.normal(0, 0.1, 40), 0.01, 0.99)
    cal = PlattCalibrator()
    result = cal.fit(y, p)
    assert result.status in ("VALID", "CALIBRATION_INVALID")
    _, res2 = select_and_fit_calibrator(y, p, prefer_isotonic_min_n=80)
    assert res2.method in ("platt", "isotonic", "none")


def test_save_load_and_corrupt(tmp_path: Path):
    X, y, names = _xy(80)
    model = train_baseline_classifier(X, y, feature_names=names, model_id="p3", model_version="1")
    bundle = save_trained_model(tmp_path, model)
    assert validate_artifact_bundle(bundle)[0]
    m2, cal, b2, status = load_trained_model_safe(tmp_path, "p3", "1")
    assert status == "ok" and m2 is not None
    dirs = list(tmp_path.rglob("bundle.json"))
    assert dirs
    dirs[0].write_text('{"model_id":"","model_version":""}', encoding="utf-8")
    m, _, _, st = load_trained_model_safe(tmp_path, "p3", "1")
    assert m is None


def test_hardware_profiles():
    assert select_profile(_snap(8192)).value == "CONSERVATIVE"
    assert select_profile(_snap(16384)).value == "BALANCED"


def test_live_safety():
    from god.ml.adaptive import AdaptiveMLOrchestrator

    s = AdaptiveMLOrchestrator().safety_assertions()
    assert s["live_authorized"] is False
    assert s["broker_orders_submitted"] == 0
