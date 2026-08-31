"""Model lifecycle hardening: integrity, checksum, schema, atomic, restart.

LIVE remains blocked. No order_send.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from god.ml.lifecycle import (
    ARTIFACT_SCHEMA_VERSION,
    check_schema_compatibility,
    load_with_integrity,
    verify_artifact_integrity,
)
from god.ml.persist import (
    load_trained_model_safe,
    save_trained_model,
    validate_artifact_bundle,
)
from god.ml.registry import ModelRegistry
from god.ml.recovery import recover_champion, check_state_consistency
from god.ml.train import train_baseline_classifier


def _xy(n: int = 60, seed: int = 7):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    y = (X[:, 0] + rng.normal(scale=0.2, size=n) > 0).astype(int)
    return X, y, tuple(f"f{i}" for i in range(3))


def test_save_includes_checksum_and_schema(tmp_path: Path):
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="lc1", model_version="1")
    bundle = save_trained_model(tmp_path, model)
    assert bundle.schema_version == ARTIFACT_SCHEMA_VERSION
    assert bundle.artifact_checksum
    assert len(bundle.artifact_checksum) == 64
    ok, reason = validate_artifact_bundle(bundle)
    assert ok and reason == "ok"


def test_integrity_ok_after_save(tmp_path: Path):
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="lc2", model_version="1")
    save_trained_model(tmp_path, model)
    rep = verify_artifact_integrity(tmp_path, "lc2", "1")
    assert rep.ok
    assert rep.status == "ok"
    assert rep.artifact_checksum


def test_checksum_mismatch_detected(tmp_path: Path):
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="lc3", model_version="1")
    save_trained_model(tmp_path, model)
    art = list((tmp_path / "artifacts").rglob("model.pkl"))[0]
    art.write_bytes(art.read_bytes() + b"\x00TAMPER")
    rep = verify_artifact_integrity(tmp_path, "lc3", "1")
    assert not rep.ok
    assert rep.status == "checksum_mismatch"
    m, _, _, status = load_trained_model_safe(tmp_path, "lc3", "1")
    assert m is None
    assert status in ("checksum_mismatch", "corrupt")


def test_corrupt_bundle_rejected(tmp_path: Path):
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="lc4", model_version="1")
    save_trained_model(tmp_path, model)
    bpath = list((tmp_path / "artifacts").rglob("bundle.json"))[0]
    bpath.write_text("{not-json", encoding="utf-8")
    rep = verify_artifact_integrity(tmp_path, "lc4", "1")
    assert not rep.ok
    assert rep.status == "corrupt"


def test_missing_artifact(tmp_path: Path):
    rep = verify_artifact_integrity(tmp_path, "nope", "9")
    assert not rep.ok
    assert rep.status == "missing"


def test_schema_compatibility_feature_mismatch(tmp_path: Path):
    X, y, names = _xy()
    model = train_baseline_classifier(
        X, y, feature_names=names, model_id="lc5", model_version="1", features_version="feat-v1"
    )
    bundle = save_trained_model(tmp_path, model)
    crep = check_schema_compatibility(bundle, expected_features_version="feat-v2")
    assert not crep.compatible
    assert any("features_version" in r for r in crep.reasons)


def test_load_with_integrity_ok(tmp_path: Path):
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="lc6", model_version="1")
    save_trained_model(tmp_path, model)
    m, cal, bundle, irep = load_with_integrity(tmp_path, "lc6", "1")
    assert irep.ok
    assert m is not None
    assert bundle is not None


def test_restart_reload_champion(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="ch1", model_version="1")
    reg.register_candidate(model)
    reg.promote_champion("ch1", "1")
    reg2 = ModelRegistry(tmp_path)
    champ = reg2.champion()
    assert champ is not None
    assert champ.model_id == "ch1"
    result, loaded = recover_champion(reg2)
    assert result.success
    assert loaded is not None
    c = check_state_consistency(reg2)
    assert c["consistent"]
    assert c["champion_count"] == 1


def test_champion_not_replaced_by_candidate(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="old", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="new", model_version="2")
    reg.register_candidate(m1)
    reg.promote_champion("old", "1")
    reg.register_candidate(m2)
    assert reg.champion().model_id == "old"
    assert reg.champion().model_version == "1"


def test_lifecycle_live_safety():
    from god.ml.adaptive import AdaptiveMLOrchestrator

    s = AdaptiveMLOrchestrator().safety_assertions()
    assert s["live_authorized"] is False
    assert s["broker_orders_submitted"] == 0
