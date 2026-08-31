"""Reliability & self-recovery: state machine, transactional promotion, recovery, health score, freshness.

LIVE remains blocked. No order_send. No test weakening.
Covers crash/interrupt simulation, corrupt artifacts, stale detection, illegal transitions.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pytest

from god.ml.audit import MLAuditTrail
from god.ml.benchmark import BenchmarkMetrics
from god.ml.freshness import evaluate_freshness, FreshnessPolicy
from god.ml.health import ModelHealthMonitor, compute_health_score
from god.ml.promotion import transactional_promote, try_promote, evaluate_promotion
from god.ml.recovery import recover_champion, recover_startup, check_state_consistency
from god.ml.registry import ModelRegistry, ModelRecord
from god.ml.state_machine import (
    is_legal_transition,
    validate_transition,
    apply_transition,
    CANDIDATE,
    CHAMPION,
    CHALLENGER,
    TRAINING,
    REJECTED,
    ROLLED_BACK,
    PROMOTION_GATE,
    OOS,
    VALIDATED,
)
from god.ml.train import train_baseline_classifier


def _xy(n: int = 60, seed: int = 7):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    y = (X[:, 0] + rng.normal(scale=0.25, size=n) > 0).astype(int)
    return X, y, tuple(f"f{i}" for i in range(3))


def test_legal_transitions():
    assert is_legal_transition(TRAINING, "validated")
    assert is_legal_transition(VALIDATED, CANDIDATE)
    assert is_legal_transition(CANDIDATE, OOS)
    assert is_legal_transition(CANDIDATE, CHALLENGER)
    assert is_legal_transition(OOS, CHALLENGER)
    assert is_legal_transition(CHALLENGER, PROMOTION_GATE)
    assert is_legal_transition(PROMOTION_GATE, CHAMPION)
    assert is_legal_transition(CHAMPION, ROLLED_BACK)
    assert not is_legal_transition(CHAMPION, CANDIDATE)
    assert not is_legal_transition(REJECTED, CHAMPION)
    assert not is_legal_transition(TRAINING, CHAMPION)
    r = validate_transition(CHAMPION, CANDIDATE)
    assert not r.allowed
    assert "illegal" in r.reason


def test_apply_transition_audits(tmp_path: Path):
    audit = MLAuditTrail(path=tmp_path / "a.jsonl")
    ok = apply_transition(CANDIDATE, CHALLENGER, model_id="m", model_version="1", audit=audit)
    assert ok.allowed
    denied = apply_transition(CHAMPION, CANDIDATE, model_id="m", model_version="1", audit=audit)
    assert not denied.allowed
    events = audit.by_type("state_transition")
    assert len(events) >= 2
    assert any(e["outcome"] == "denied" for e in events)


def test_health_score_deterministic():
    s1 = compute_health_score(oos_accuracy=0.60, brier=0.20, artifact_ok=True)
    s2 = compute_health_score(oos_accuracy=0.60, brier=0.20, artifact_ok=True)
    assert s1 == s2
    assert 0.0 <= s1 <= 1.0
    bad = compute_health_score(oos_accuracy=0.40, artifact_ok=False)
    assert bad < s1
    stale = compute_health_score(oos_accuracy=0.60, model_stale=True)
    assert stale < s1
    recovery_fail = compute_health_score(oos_accuracy=0.60, recovery_failed=True)
    assert recovery_fail < s1


def test_health_score_in_report(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m = train_baseline_classifier(X, y, feature_names=names, model_id="hs", model_version="1")
    reg.register_candidate(m)
    reg.promote_champion("hs", "1")
    mon = ModelHealthMonitor(registry=reg)
    report = mon.evaluate(recent_oos_accuracy=0.58, recent_brier=0.22)
    assert "health_score" in report.metrics
    assert report.health_score > 0


def test_health_degraded_on_stale_and_recovery(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m = train_baseline_classifier(X, y, feature_names=names, model_id="st", model_version="1")
    reg.register_candidate(m)
    reg.promote_champion("st", "1")
    mon = ModelHealthMonitor(registry=reg)
    report = mon.evaluate(model_stale=True, recovery_failed=False)
    assert "model_stale" in report.reasons
    assert report.status in ("DEGRADED", "CRITICAL")
    report2 = mon.evaluate(recovery_failed=True)
    assert report2.prefer_no_trade
    assert report2.status == "CRITICAL"


def test_transactional_promote_success(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="old", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="new", model_version="2")
    reg.register_candidate(m1)
    reg.promote_champion("old", "1")
    reg.register_candidate(m2)
    for r in reg.list_models():
        if r.model_id == "new":
            r.oos_metrics = {"accuracy": 0.70, "brier": 0.15, "n": 50}
    oos = BenchmarkMetrics(accuracy=0.70, brier=0.15, n=50, log_loss=0.5)
    audit = MLAuditTrail()
    result = transactional_promote(
        reg, "new", "2", challenger_oos=oos, audit=audit
    )
    assert result.success, result.reason
    assert reg.champion().model_id == "new"
    assert "champion_pointer_updated" in result.steps_completed
    assert "post_verify_ok" in result.steps_completed


def test_transactional_promote_rejects_weak_oos(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="c1", model_version="1")
    reg.register_candidate(m1)
    oos = BenchmarkMetrics(accuracy=0.40, brier=0.40, n=50, log_loss=1.0)
    result = transactional_promote(reg, "c1", "1", challenger_oos=oos)
    assert not result.success
    assert (
        result.reason in ("oos_accuracy_below_threshold", "brier_too_high", "insufficient_oos_n")
        or "oos" in result.reason
        or "brier" in result.reason
    )


def test_transactional_promote_integrity_fail(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m = train_baseline_classifier(X, y, feature_names=names, model_id="bad", model_version="1")
    reg.register_candidate(m)
    for art in (tmp_path / "artifacts").rglob("model.pkl"):
        art.write_bytes(b"corrupt")
        break
    oos = BenchmarkMetrics(accuracy=0.80, brier=0.10, n=100, log_loss=0.3)
    result = transactional_promote(reg, "bad", "1", challenger_oos=oos)
    assert not result.success
    assert "integrity" in result.reason


def test_transactional_promote_crash_before_commit_leaves_old(tmp_path: Path):
    """Simulate pre-commit failure: integrity fails → old champion remains."""
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="old", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="new", model_version="2")
    reg.register_candidate(m1)
    reg.promote_champion("old", "1")
    reg.register_candidate(m2)
    for art in (tmp_path / "artifacts").rglob("model.pkl"):
        if "new@2" in str(art) or "new" in str(art.parent):
            art.write_bytes(b"corrupt_pre_commit")
            break
    oos = BenchmarkMetrics(accuracy=0.90, brier=0.05, n=100, log_loss=0.2)
    result = transactional_promote(reg, "new", "2", challenger_oos=oos)
    assert not result.success
    champ = reg.champion()
    assert champ is not None
    assert champ.model_id == "old"


def test_recovery_corrupt_champion_fallback(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="old", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="new", model_version="2")
    reg.register_candidate(m1)
    reg.promote_champion("old", "1")
    reg.register_candidate(m2)
    reg.promote_champion("new", "2")
    for art in (tmp_path / "artifacts").rglob("model.pkl"):
        if "new@2" in str(art) or (art.parent.name.startswith("new") and "2" in art.parent.name):
            art.write_bytes(b"corrupt")
            break
    result, loaded = recover_champion(reg, try_previous_on_corrupt=True)
    if result.success:
        assert loaded is not None
        assert result.model_id == "old"
    else:
        assert result.prefer_no_trade


def test_recovery_both_corrupt_safe_only(tmp_path: Path):
    """If champion and previous are both corrupt → SAFE_ONLY / prefer_no_trade."""
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="old", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="new", model_version="2")
    reg.register_candidate(m1)
    reg.promote_champion("old", "1")
    reg.register_candidate(m2)
    reg.promote_champion("new", "2")
    for art in (tmp_path / "artifacts").rglob("model.pkl"):
        art.write_bytes(b"corrupt_all")
    result, loaded = recover_champion(reg, try_previous_on_corrupt=True)
    assert not result.success
    assert result.prefer_no_trade
    assert loaded is None
    assert result.status in ("safe_only", "corrupt")


def test_recover_startup_no_champion(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    result, loaded = recover_startup(reg)
    assert not result.success
    assert result.prefer_no_trade
    assert loaded is None


def test_state_consistency_ok(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m = train_baseline_classifier(X, y, feature_names=names, model_id="ok", model_version="1")
    reg.register_candidate(m)
    reg.promote_champion("ok", "1")
    c = check_state_consistency(reg)
    assert c["consistent"]
    assert c["champion_count"] == 1


def test_state_consistency_multiple_champions(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="a", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="b", model_version="1")
    reg.register_candidate(m1)
    reg.register_candidate(m2)
    for r in reg.list_models():
        r.status = "champion"
    reg._save()
    c = check_state_consistency(reg)
    assert not c["consistent"]
    assert "multiple_champions" in str(c["issues"])
    result, loaded = recover_startup(reg)
    assert not result.success
    assert result.prefer_no_trade


def test_hardware_cannot_promote(tmp_path: Path):
    rec = ModelRecord(
        model_id="h",
        model_version="1",
        status="candidate",
        features_version="1",
        dataset_hash="x",
        oos_metrics={"accuracy": 0.9, "brier": 0.1, "n": 100},
    )
    gate = evaluate_promotion(rec, hardware_only=True)
    assert not gate.allowed
    assert "hardware" in gate.reason


def test_freshness_fresh():
    now = datetime.now(timezone.utc)
    saved = (now - timedelta(hours=1)).isoformat()
    report = evaluate_freshness(model_saved_at=saved, dataset_built_at=saved)
    assert report.ok
    assert report.status == "fresh"
    assert not report.prefer_no_trade


def test_freshness_stale_model():
    now = datetime.now(timezone.utc)
    saved = (now - timedelta(hours=200)).isoformat()
    report = evaluate_freshness(model_saved_at=saved, now_ts=now.timestamp())
    assert not report.ok
    assert report.status == "stale_model"
    assert "model_stale" in report.reasons


def test_freshness_hard_stale_prefer_no_trade():
    now = datetime.now(timezone.utc)
    saved = (now - timedelta(hours=800)).isoformat()
    report = evaluate_freshness(model_saved_at=saved, now_ts=now.timestamp())
    assert not report.ok
    assert report.prefer_no_trade
    assert "model_hard_stale" in report.reasons


def test_freshness_stale_dataset():
    now = datetime.now(timezone.utc)
    ds = (now - timedelta(hours=100)).isoformat()
    model = (now - timedelta(hours=1)).isoformat()
    report = evaluate_freshness(model_saved_at=model, dataset_built_at=ds, now_ts=now.timestamp())
    assert not report.ok
    assert report.status == "stale_dataset"


def test_freshness_unknown_no_timestamps():
    report = evaluate_freshness()
    assert report.status == "unknown"
    assert report.ok  # missing timestamps do not auto-fail


def test_reliability_live_safety():
    from god.ml.adaptive import AdaptiveMLOrchestrator

    s = AdaptiveMLOrchestrator().safety_assertions()
    assert s["live_authorized"] is False
    assert s["broker_orders_submitted"] == 0


def test_optional_ml_missing_graceful():
    """Selector / capabilities must not crash when heavy deps absent."""
    from god.ml.model_capabilities import detect_model_capabilities, allowed_families_for_limits
    from god.ml.hardware import ResourceLimits, HardwareProfile

    caps = detect_model_capabilities(gpu_available=False)
    assert "numpy_logit" in caps
    assert caps["numpy_logit"].available
    limits = ResourceLimits(
        profile=HardwareProfile.CONSERVATIVE,
        max_workers=1,
        allow_heavy_ml=False,
        allowed_families=("numpy_logit", "random_forest", "lightgbm", "lstm"),
        memory_budget_mb=2048,
    )
    families = allowed_families_for_limits(limits, caps)
    assert "numpy_logit" in families
    assert "lstm" not in families
