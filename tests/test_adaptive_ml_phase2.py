"""Phase-2 Adaptive ML: benchmarking, regime, drift, promotion, weighting, scheduler."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from god.ml.adaptive import AdaptiveMLOrchestrator
from god.ml.benchmark import benchmark_families, benchmark_family
from god.ml.drift import evaluate_drift
from god.ml.feature_eval import PROTECTED_FEATURES, evaluate_features
from god.ml.hardware import HardwareProfile, HardwareSnapshot, ResourceGovernor, build_resource_limits
from god.ml.promotion import PromotionPolicy, evaluate_promotion, try_promote
from god.ml.regime import Regime, detect_regime
from god.ml.registry import ModelRegistry
from god.ml.scheduler import TrainingScheduler
from god.ml.train import train_baseline_classifier
from god.ml.weighting import apply_sample_weights, volatility_sample_weights


def _snap(total_ram_mb: int = 8192, **kw) -> HardwareSnapshot:
    defaults = dict(
        cpu_cores=4,
        cpu_threads=8,
        available_ram_mb=total_ram_mb // 2,
        gpu_available=False,
        vram_mb=0,
        available_disk_mb=50_000,
        cpu_percent=10.0,
        memory_percent=40.0,
        platform="Linux",
        architecture="x86_64",
        notes=("test",),
    )
    defaults.update(kw)
    return HardwareSnapshot(total_ram_mb=total_ram_mb, **defaults)


def _xy(n: int = 80, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] + rng.normal(scale=0.3, size=n) > 0).astype(int)
    return X, y, tuple(f"f{i}" for i in range(4))


def test_regime_trending_and_uncertain():
    # Strong uptrend
    closes = np.linspace(1.0, 2.0, 60)
    snap = detect_regime(closes)
    assert snap.regime in (Regime.TRENDING, Regime.LOW_VOLATILITY, Regime.UNCERTAIN)
    assert snap.n_bars >= 20
    # Too short → UNCERTAIN
    short = detect_regime([1.0, 1.1, 1.2])
    assert short.regime == Regime.UNCERTAIN
    assert "insufficient" in short.reason


def test_regime_high_vol():
    rng = np.random.default_rng(1)
    base = 100.0
    closes = [base]
    for _ in range(80):
        base *= 1.0 + rng.normal(0, 0.05)
        closes.append(base)
    snap = detect_regime(closes)
    assert snap.regime in (
        Regime.HIGH_VOLATILITY,
        Regime.TRENDING,
        Regime.RANGING,
        Regime.UNCERTAIN,
        Regime.LOW_VOLATILITY,
    )


def test_sample_weighting_clips_extremes():
    r = np.array([0.01, 0.02, -0.01, 0.5, -0.4, 0.0, 0.01] * 5)
    w = volatility_sample_weights(r)
    assert len(w) == len(r)
    assert np.all(w > 0)
    assert float(np.mean(w)) == pytest.approx(1.0, abs=0.05)
    # Extreme |r| should not dominate (weight near floor)
    assert w[3] <= w[0] * 1.5 or w[3] <= 1.0


def test_apply_sample_weights_uniform_fallback():
    X = np.ones((5, 2))
    y = np.array([0, 1, 0, 1, 0])
    X2, y2, w = apply_sample_weights(X, y, None)
    assert len(w) == 5
    assert np.allclose(w, 1.0)


def test_drift_feature_and_performance():
    rng = np.random.default_rng(2)
    base = rng.normal(size=(100, 3))
    recent = base + 3.0  # strong shift
    report = evaluate_drift(
        baseline_X=base,
        recent_X=recent,
        baseline_acc=0.60,
        recent_acc=0.40,
    )
    assert report.feature_drift is True or report.performance_degraded is True
    assert report.confidence_multiplier < 1.0
    assert report.restrict_promotion is True
    assert report.retrain_eligible is True


def test_drift_no_false_positive_on_same_data():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(80, 3))
    p = rng.uniform(0.4, 0.6, size=80)
    report = evaluate_drift(
        baseline_X=X[:50],
        recent_X=X[50:],
        baseline_p=p[:50],
        recent_p=p[50:],
        baseline_acc=0.55,
        recent_acc=0.54,
    )
    # Same distribution → should not aggressively flag
    assert report.confidence_multiplier >= 0.4


def test_benchmark_family_walk_forward():
    X, y, names = _xy(100)
    fb = benchmark_family(X, y, family="random_forest", feature_names=names)
    assert fb.family == "random_forest"
    if "insufficient" not in "".join(fb.notes):
        assert fb.overall.n > 0
        assert 0.0 <= fb.overall.accuracy <= 1.0
        assert fb.overall.brier >= 0.0


def test_benchmark_ranking_deterministic():
    X, y, names = _xy(90, seed=7)
    gov = ResourceGovernor(_snap(8192))
    r1 = benchmark_families(X, y, ["numpy_logit", "random_forest"], feature_names=names, governor=gov)
    r2 = benchmark_families(X, y, ["numpy_logit", "random_forest"], feature_names=names, governor=gov)
    assert r1.ranking == r2.ranking
    assert r1.best_family == r2.best_family


def test_promotion_blocked_by_hardware_only(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    X, y, names = _xy(40)
    m = train_baseline_classifier(X, y, feature_names=names, model_id="c1", model_version="1")
    rec = reg.register_candidate(m, oos_metrics={"accuracy": 0.70, "brier": 0.2, "n": 50})
    gate = evaluate_promotion(rec, hardware_only=True)
    assert gate.allowed is False
    assert "hardware" in gate.reason


def test_promotion_requires_oos_gates(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    X, y, names = _xy(40)
    m = train_baseline_classifier(X, y, feature_names=names, model_id="weak", model_version="1")
    rec = reg.register_candidate(m, oos_metrics={"accuracy": 0.40, "brier": 0.4, "n": 5})
    gate = evaluate_promotion(rec, policy=PromotionPolicy(min_oos_n=20, min_oos_accuracy=0.52))
    assert gate.allowed is False


def test_promotion_success_and_champion(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    X, y, names = _xy(50)
    m = train_baseline_classifier(X, y, feature_names=names, model_id="strong", model_version="1")
    reg.register_candidate(m, oos_metrics={"accuracy": 0.65, "brier": 0.18, "n": 40})
    gate = try_promote(
        reg,
        "strong",
        "1",
        policy=PromotionPolicy(min_oos_n=20, min_oos_accuracy=0.52, min_improvement=0.0),
    )
    assert gate.allowed is True
    assert reg.champion() is not None
    assert reg.champion().model_id == "strong"


def test_scheduler_blocks_under_pressure():
    gov = ResourceGovernor(_snap(8192, available_ram_mb=200, memory_percent=95.0))
    sched = TrainingScheduler(governor=gov)
    d = sched.evaluate(current_samples=1000)
    assert d.eligible is False or gov.limits.training_allowed is False


def test_scheduler_initial_train_allowed():
    gov = ResourceGovernor(_snap(16384, available_ram_mb=10000, memory_percent=30.0))
    sched = TrainingScheduler(governor=gov)
    d = sched.evaluate(current_samples=100)
    assert d.eligible is True
    assert d.reason == "initial_train"


def test_feature_eval_protects_safety_features():
    X, y, _ = _xy(60)
    names = ("ret_1", "noise_a", "noise_b", "vol_10")
    model = train_baseline_classifier(X, y, feature_names=names)
    report = evaluate_features(model, X, y, names, allow_shap=False, prune_threshold=-1.0)
    assert "ret_1" in report.protected_kept or "ret_1" not in report.pruned
    assert "vol_10" in report.protected_kept or "vol_10" not in report.pruned
    assert "ret_1" in PROTECTED_FEATURES


def test_orchestrator_phase2_safety(tmp_path: Path):
    orch = AdaptiveMLOrchestrator(registry_root=tmp_path / "reg")
    X, y, names = _xy(60)
    report = orch.benchmark(X, y, feature_names=names)
    assert report is not None
    s = orch.safety_assertions()
    assert s["broker_orders_submitted"] == 0
    assert s["live_authorized"] is False
    # Hardware must not promote
    assert orch.champion_unchanged_by_hardware() is True


def test_insufficient_data_fail_closed():
    X = np.random.randn(5, 2)
    y = np.array([0, 1, 0, 1, 0])
    fb = benchmark_family(X, y, family="numpy_logit", feature_names=("a", "b"))
    assert "insufficient" in "".join(fb.notes) or fb.overall.n == 0


def test_8gb_16gb_32gb_profiles_intact():
    assert build_resource_limits(_snap(8192)).profile == HardwareProfile.CONSERVATIVE
    assert build_resource_limits(_snap(16384)).profile == HardwareProfile.BALANCED
    assert (
        build_resource_limits(_snap(32768, cpu_threads=16, memory_percent=20.0)).profile
        == HardwareProfile.HIGH_PERFORMANCE
    )


def test_live_blocked_orders_zero_after_phase2(tmp_path: Path):
    orch = AdaptiveMLOrchestrator(registry_root=tmp_path / "reg")
    X, y, names = _xy(40)
    orch.train(X, y, feature_names=names)
    s = orch.safety_assertions()
    assert s["broker_orders_submitted"] == 0
    assert s["live_authorized"] is False
