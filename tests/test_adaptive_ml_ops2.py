"""Production-grade ops-2: data quality, config validation, graceful degradation.

LIVE remains blocked. No order_send.
"""
from __future__ import annotations

import numpy as np
import pytest

from god.ml.config_validate import MLRuntimeConfig, validate_ml_config
from god.ml.data_quality import DataQualityPolicy, evaluate_data_quality
from god.ml.degradation import evaluate_degradation
from god.ml.hardware import HardwareProfile


def _xy(n: int = 80, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] + rng.normal(scale=0.3, size=n) > 0).astype(int)
    return X, y


def test_data_quality_ok():
    X, y = _xy()
    r = evaluate_data_quality(X, y)
    assert r.status == "OK"
    assert not r.restrict_training
    assert not r.prefer_no_trade
    assert r.metrics["n_samples"] == 80


def test_data_quality_insufficient():
    X = np.zeros((5, 2))
    y = np.array([0, 1, 0, 1, 0])
    r = evaluate_data_quality(X, y, policy=DataQualityPolicy(min_samples=30))
    assert r.status == "FAIL"
    assert r.restrict_training
    assert "insufficient_samples" in r.reasons


def test_data_quality_nan():
    X, y = _xy()
    X[0, 0] = np.nan
    X[1, 1] = np.nan
    # raise nan frac above threshold
    X[:, 2] = np.nan
    r = evaluate_data_quality(X, y, policy=DataQualityPolicy(max_nan_frac=0.01))
    assert r.status in ("WARN", "FAIL")
    assert "high_nan_frac" in r.reasons


def test_data_quality_single_class():
    X, _ = _xy()
    y = np.zeros(len(X), dtype=int)
    r = evaluate_data_quality(X, y)
    assert r.status == "FAIL"
    assert "single_class" in r.reasons
    assert r.prefer_no_trade


def test_data_quality_zero_variance():
    X = np.ones((50, 4))
    y = np.array([0, 1] * 25)
    r = evaluate_data_quality(X, y)
    assert r.status in ("WARN", "FAIL")
    assert "feature_variance_collapse" in r.reasons


def test_config_validate_defaults():
    r = validate_ml_config(None)
    assert r.valid
    assert r.normalized["live_authorized"] is False
    assert r.normalized["broker_orders_submitted"] == 0
    assert r.normalized["inference_priority"] is True


def test_config_validate_blocks_live():
    r = validate_ml_config({"live_authorized": True, "meta_enabled": True})
    assert not r.valid
    assert any("forbidden_true" in x for x in r.reasons)
    # normalized still forces safety
    assert r.normalized["live_authorized"] is False


def test_config_validate_rejects_bad_ensemble():
    r = validate_ml_config({"max_ensemble_size": 99})
    assert not r.valid
    assert "max_ensemble_size_out_of_range" in r.reasons


def test_config_validate_normalizes_bounds():
    r = validate_ml_config({"telemetry_max_events": 3, "min_samples_train": 100})
    # telemetry clamped up to min 10, but valid still true for that field
    assert r.normalized["telemetry_max_events"] >= 10
    assert r.normalized["min_samples_train"] == 100


def test_degradation_conservative():
    d = evaluate_degradation(profile=HardwareProfile.CONSERVATIVE)
    assert d.mode in ("REDUCED", "MINIMAL", "SAFE_ONLY")
    assert d.max_ensemble <= 1
    assert not d.allow_heavy_ml


def test_degradation_resource_pressure():
    d = evaluate_degradation(
        profile=HardwareProfile.HIGH_PERFORMANCE,
        resource_pressure=True,
    )
    assert not d.allow_training
    assert not d.allow_heavy_ml
    assert d.max_ensemble <= 1
    assert "resource_pressure" in d.reasons


def test_degradation_data_quality_fail():
    d = evaluate_degradation(data_quality_status="FAIL")
    assert d.mode == "SAFE_ONLY"
    assert d.prefer_no_trade
    assert not d.allow_training


def test_degradation_health_critical():
    d = evaluate_degradation(health_status="CRITICAL")
    assert d.mode == "SAFE_ONLY"
    assert d.prefer_no_trade


def test_degradation_full_healthy():
    d = evaluate_degradation(
        profile=HardwareProfile.HIGH_PERFORMANCE,
        health_status="HEALTHY",
        data_quality_status="OK",
        resource_pressure=False,
    )
    assert d.mode == "FULL"
    assert d.allow_training
    assert not d.prefer_no_trade


def test_ops2_live_safety():
    from god.ml.adaptive import AdaptiveMLOrchestrator

    s = AdaptiveMLOrchestrator().safety_assertions()
    assert s["live_authorized"] is False
    assert s["broker_orders_submitted"] == 0

    cfg = validate_ml_config({"enable_live": True})
    assert not cfg.valid
    assert cfg.normalized["live_authorized"] is False
