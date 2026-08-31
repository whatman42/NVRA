"""Regression tests for zero-config hardware-adaptive ML.

Covers CONSERVATIVE (8 GB) with RF + lightweight LGB/XGB, BALANCED (12–16 GB),
HIGH_PERFORMANCE (≥32 GB), GPU/no-GPU, optional deps, pressure, inference priority,
ensemble constraints, upgrade/downgrade, champion stability, registry portability,
deterministic selection, LIVE blocked, broker_orders_submitted == 0.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from god.ml.adaptive import AdaptiveMLOrchestrator
from god.ml.ensemble import train_constrained_ensemble
from god.ml.hardware import (
    HardwareProfile,
    HardwareSnapshot,
    ResourceGovernor,
    build_resource_limits,
    detect_hardware,
    select_profile,
)
from god.ml.meta_label import MetaLabeler
from god.ml.model_capabilities import ModelCapabilityRegistry, detect_model_capabilities
from god.ml.prediction import Direction, Prediction, PredictionStatus
from god.ml.registry import ModelRegistry
from god.ml.retention import RetentionPolicy, apply_retention
from god.ml.selector import AdaptiveModelSelector
from god.ml.train import train_baseline_classifier


def _snap(
    total_ram_mb: int = 8192,
    available_ram_mb: int = 4096,
    cpu_threads: int = 4,
    cpu_cores: int = 2,
    gpu: bool = False,
    vram: int = 0,
    cpu_pct: float = 10.0,
    mem_pct: float = 40.0,
    disk_mb: int = 50_000,
) -> HardwareSnapshot:
    return HardwareSnapshot(
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        total_ram_mb=total_ram_mb,
        available_ram_mb=available_ram_mb,
        gpu_available=gpu,
        vram_mb=vram,
        available_disk_mb=disk_mb,
        cpu_percent=cpu_pct,
        memory_percent=mem_pct,
        platform="Linux",
        architecture="x86_64",
        notes=("test",),
    )


def test_detect_hardware_never_raises():
    snap = detect_hardware()
    assert isinstance(snap, HardwareSnapshot)
    assert snap.cpu_threads >= 1
    assert snap.cpu_cores >= 1
    assert isinstance(snap.gpu_available, bool)


def test_8gb_conservative_profile():
    snap = _snap(total_ram_mb=8192, available_ram_mb=3500)
    assert select_profile(snap) == HardwareProfile.CONSERVATIVE
    limits = build_resource_limits(snap)
    assert limits.profile == HardwareProfile.CONSERVATIVE
    assert limits.max_workers == 1
    assert limits.max_parallel_train_jobs == 1
    assert limits.allow_ensemble is False
    assert limits.allow_heavy_ml is False
    assert limits.sequential_training is True
    assert limits.inference_priority is True
    assert "lstm" not in limits.allowed_families
    assert "transformer" not in limits.allowed_families
    assert "gru" not in limits.allowed_families


def test_8gb_allows_rf_and_lightweight_boosters():
    """8 GB must NOT be RF-only: LightGBM/XGBoost remain policy-eligible."""
    snap = _snap(total_ram_mb=8192, available_ram_mb=4000, mem_pct=40.0)
    limits = build_resource_limits(snap)
    assert "random_forest" in limits.allowed_families
    assert "numpy_logit" in limits.allowed_families
    assert "lightgbm" in limits.allowed_families
    assert "xgboost" in limits.allowed_families
    assert "catboost" not in limits.allowed_families  # BALANCED+
    assert "lstm" not in limits.allowed_families


def test_12gb_balanced():
    snap = _snap(total_ram_mb=12288, available_ram_mb=8000, cpu_threads=6)
    assert select_profile(snap) == HardwareProfile.BALANCED
    limits = build_resource_limits(snap)
    assert limits.profile == HardwareProfile.BALANCED
    assert limits.allow_heavy_ml is False
    assert "catboost" in limits.allowed_families
    assert "lightgbm" in limits.allowed_families
    assert "xgboost" in limits.allowed_families


def test_16gb_is_balanced_not_high_performance():
    """CRITICAL: 16 GB must remain BALANCED, never auto HIGH_PERFORMANCE."""
    snap = _snap(total_ram_mb=16384, available_ram_mb=12000, cpu_threads=8, mem_pct=30.0)
    assert select_profile(snap) == HardwareProfile.BALANCED
    limits = build_resource_limits(snap)
    assert limits.profile == HardwareProfile.BALANCED
    assert limits.allow_heavy_ml is False


def test_32gb_high_performance():
    snap = _snap(
        total_ram_mb=32768,
        available_ram_mb=20000,
        cpu_threads=16,
        cpu_cores=8,
        gpu=True,
        vram=8192,
        mem_pct=30.0,
        cpu_pct=20.0,
    )
    assert select_profile(snap) == HardwareProfile.HIGH_PERFORMANCE
    limits = build_resource_limits(snap)
    assert limits.profile == HardwareProfile.HIGH_PERFORMANCE
    assert limits.allow_ensemble is True
    assert limits.allow_heavy_ml is True
    assert limits.max_ensemble_size >= 3


def test_gpu_detected_and_unavailable_fallback():
    snap_gpu = _snap(total_ram_mb=32768, cpu_threads=16, gpu=True, vram=8192)
    limits_gpu = build_resource_limits(snap_gpu)
    assert limits_gpu.allow_heavy_ml is True

    snap_no = _snap(total_ram_mb=32768, cpu_threads=16, gpu=False, vram=0)
    limits_no = build_resource_limits(snap_no)
    assert limits_no.profile == HardwareProfile.HIGH_PERFORMANCE
    assert limits_no.allow_heavy_ml is False  # no GPU → no heavy


def test_optional_heavy_ml_unavailable_graceful():
    caps = detect_model_capabilities(gpu_available=False)
    for fam in ("lstm", "gru", "transformer"):
        assert fam in caps
        assert isinstance(caps[fam].dependency_available, bool)
        assert caps[fam].is_heavy is True
        assert caps[fam].min_profile == HardwareProfile.HIGH_PERFORMANCE
        assert caps[fam].gpu_required is True


def test_resource_pressure_reduces_concurrency():
    snap = _snap(
        total_ram_mb=32768,
        available_ram_mb=800,
        cpu_threads=16,
        mem_pct=90.0,
        cpu_pct=88.0,
    )
    limits = build_resource_limits(snap)
    assert limits.max_workers == 1
    assert limits.max_parallel_train_jobs == 1
    assert limits.sequential_training is True
    assert limits.max_ensemble_size <= 1


def test_inference_priority_and_training_deferred():
    gov = ResourceGovernor(_snap(total_ram_mb=8192, available_ram_mb=400, mem_pct=92.0))
    assert gov.limits.inference_priority is True
    assert gov.limits.training_allowed is False or gov.may_start_training() is False
    gov._training_active = True
    assert gov.may_start_training() is False or gov.limits.max_parallel_train_jobs <= 1


def test_ensemble_constrained_on_conservative():
    snap = _snap(total_ram_mb=8192)
    gov = ResourceGovernor(snap)
    assert gov.limits.allow_ensemble is False
    assert gov.limits.max_ensemble_size == 1
    rng = np.random.default_rng(0)
    X = rng.normal(size=(40, 4))
    y = (rng.random(40) > 0.5).astype(int)
    result = train_constrained_ensemble(
        X, y, feature_names=tuple(f"f{i}" for i in range(4)), governor=gov
    )
    assert len(result.members) <= 1
    assert "ensemble_disabled" in result.notes or result.sequential is True


def test_ensemble_increases_on_high_performance():
    snap = _snap(
        total_ram_mb=32768, available_ram_mb=20000, cpu_threads=16, mem_pct=25.0
    )
    limits = build_resource_limits(snap)
    assert limits.allow_ensemble is True
    assert limits.max_ensemble_size >= 3


def test_hardware_upgrade_increases_capability():
    low = build_resource_limits(_snap(total_ram_mb=8192, cpu_threads=4))
    mid = build_resource_limits(_snap(total_ram_mb=16384, cpu_threads=8))
    high = build_resource_limits(
        _snap(total_ram_mb=32768, cpu_threads=16, gpu=True, vram=8192, mem_pct=20.0)
    )
    assert low.profile == HardwareProfile.CONSERVATIVE
    assert mid.profile == HardwareProfile.BALANCED
    assert high.profile == HardwareProfile.HIGH_PERFORMANCE
    assert len(high.allowed_families) >= len(mid.allowed_families)
    assert high.max_ensemble_size >= mid.max_ensemble_size


def test_hardware_downgrade_reduces_safely():
    high = build_resource_limits(
        _snap(total_ram_mb=32768, cpu_threads=16, mem_pct=20.0)
    )
    low = build_resource_limits(_snap(total_ram_mb=8192, cpu_threads=4))
    assert low.profile == HardwareProfile.CONSERVATIVE
    assert low.allow_heavy_ml is False
    assert low.max_workers <= high.max_workers


def test_deterministic_selection():
    snap = _snap(total_ram_mb=8192)
    gov = ResourceGovernor(snap)
    sel = AdaptiveModelSelector(governor=gov)
    a = sel.select()
    b = sel.select()
    assert a.selected == b.selected
    assert a.eligible == b.eligible
    assert a.profile == HardwareProfile.CONSERVATIVE


def test_selector_prefers_champion_family(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    X = np.random.randn(30, 3)
    y = (np.random.rand(30) > 0.5).astype(int)
    model = train_baseline_classifier(
        X, y, feature_names=("a", "b", "c"), model_id="random_forest", model_version="1"
    )
    reg.register_candidate(model, model_family="random_forest")
    reg.promote_champion("random_forest", "1")
    gov = ResourceGovernor(_snap(total_ram_mb=8192))
    sel = AdaptiveModelSelector(governor=gov, registry=reg)
    result = sel.select()
    assert result.selected == "random_forest"
    assert "prefer_champion_family" in result.notes


def test_model_registry_metadata_persistence(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    X = np.random.randn(30, 3)
    y = (np.random.rand(30) > 0.5).astype(int)
    model = train_baseline_classifier(
        X, y, feature_names=("a", "b", "c"), model_id="rf_test", model_version="1"
    )
    model.metadata["hardware_profile"] = "CONSERVATIVE"
    rec = reg.register_candidate(
        model,
        hardware_profile="CONSERVATIVE",
        model_family="random_forest",
        oos_metrics={"oos_acc": 0.55},
    )
    assert rec.hardware_profile == "CONSERVATIVE"
    assert rec.model_family == "random_forest"
    assert rec.oos_metrics.get("oos_acc") == 0.55
    reg2 = ModelRegistry(tmp_path / "reg")
    found = [r for r in reg2.list_models() if r.model_id == "rf_test"]
    assert len(found) == 1
    assert found[0].hardware_profile == "CONSERVATIVE"


def test_champion_not_changed_by_hardware(tmp_path: Path):
    orch = AdaptiveMLOrchestrator(registry_root=tmp_path / "reg")
    X = np.random.randn(40, 3)
    y = (np.random.rand(40) > 0.5).astype(int)
    model = train_baseline_classifier(
        X, y, feature_names=("a", "b", "c"), model_id="champ", model_version="1"
    )
    orch.registry.register_candidate(model)
    orch.registry.promote_champion("champ", "1")
    before = orch.registry.champion()
    assert before is not None
    assert orch.champion_unchanged_by_hardware() is True
    after = orch.registry.champion()
    assert after is not None
    assert after.model_id == before.model_id
    assert after.model_version == before.model_version


def test_meta_label_disabled_passthrough():
    meta = MetaLabeler(enabled=False)
    pred = Prediction(
        model_id="m",
        model_version="1",
        timestamp="t",
        symbol="EURUSD",
        timeframe="H1",
        direction=Direction.UP,
        probability=0.7,
        confidence=0.4,
        features_version="feat-v1",
        status=PredictionStatus.VALID,
    )
    d = meta.decide(pred)
    assert d.enabled is False
    assert d.take is True


def test_meta_label_fail_closed_without_features():
    model = train_baseline_classifier(
        np.random.randn(20, 2),
        (np.random.rand(20) > 0.5).astype(int),
        feature_names=("x", "y"),
    )
    meta = MetaLabeler(meta_model=model, enabled=True)
    pred = Prediction(
        model_id="m",
        model_version="1",
        timestamp="t",
        symbol="EURUSD",
        timeframe="H1",
        direction=Direction.UP,
        probability=0.8,
        confidence=0.6,
        features_version="feat-v1",
        status=PredictionStatus.VALID,
    )
    d = meta.decide(pred, features=None)
    assert d.take is False
    assert "fail_closed" in d.reason


def test_retention_protects_champion(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    for i in range(5):
        m = train_baseline_classifier(
            np.random.randn(20, 2),
            (np.random.rand(20) > 0.5).astype(int),
            feature_names=("x", "y"),
            model_id=f"m{i}",
            model_version="1",
        )
        reg.register_candidate(m)
    reg.promote_champion("m0", "1")
    policy = RetentionPolicy(max_candidates=2, max_retired=1)
    result = apply_retention(reg, policy)
    assert result["champion_protected"] is True
    champ = reg.champion()
    assert champ is not None
    assert champ.model_id == "m0"


def test_adaptive_orchestrator_safety(tmp_path: Path):
    orch = AdaptiveMLOrchestrator(registry_root=tmp_path / "reg")
    ctx = orch.context()
    assert ctx.profile in (
        HardwareProfile.CONSERVATIVE,
        HardwareProfile.BALANCED,
        HardwareProfile.HIGH_PERFORMANCE,
    )
    assert ctx.selection is not None
    safety = orch.safety_assertions()
    assert safety["broker_orders_submitted"] == 0
    assert safety["live_authorized"] is False
    assert safety["inference_priority"] is True


def test_capability_registry_runnable_conservative():
    caps = ModelCapabilityRegistry()
    limits = build_resource_limits(_snap(total_ram_mb=8192))
    runnable = caps.runnable(limits)
    assert "numpy_logit" in runnable or "random_forest" in runnable
    assert "lstm" not in runnable
    assert "transformer" not in runnable


def test_live_remains_blocked_and_orders_zero(tmp_path: Path):
    orch = AdaptiveMLOrchestrator(registry_root=tmp_path / "reg")
    X = np.random.randn(30, 3)
    y = (np.random.rand(30) > 0.5).astype(int)
    orch.train(X, y, feature_names=("a", "b", "c"))
    s = orch.safety_assertions()
    assert s["broker_orders_submitted"] == 0
    assert s["live_authorized"] is False


def test_validation_still_required_for_promotion(tmp_path: Path):
    """Hardware alone must not promote; champion requires explicit promote_champion."""
    reg = ModelRegistry(tmp_path / "reg")
    m = train_baseline_classifier(
        np.random.randn(20, 2),
        (np.random.rand(20) > 0.5).astype(int),
        feature_names=("x", "y"),
        model_id="cand",
        model_version="1",
    )
    reg.register_candidate(m, hardware_profile="HIGH_PERFORMANCE", model_family="xgboost")
    assert reg.champion() is None  # not auto-promoted
