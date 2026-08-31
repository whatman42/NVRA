"""Production hardening: manifest, safe rollback, calibration metadata.

LIVE remains blocked. No order_send.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from god.ml.manifest import (
    ArtifactManifest,
    build_manifest_from_bundle,
    save_manifest,
    load_manifest,
    validate_manifest,
    verify_manifest_against_disk,
    feature_schema_hash,
)
from god.ml.persist import save_trained_model
from god.ml.registry import ModelRegistry
from god.ml.rollback_safe import safe_rollback
from god.ml.train import train_baseline_classifier
from god.ml.lifecycle import verify_artifact_integrity


def _xy(n: int = 60, seed: int = 11):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    y = (X[:, 0] + rng.normal(scale=0.25, size=n) > 0).astype(int)
    return X, y, tuple(f"f{i}" for i in range(3))


def test_manifest_build_and_validate(tmp_path: Path):
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="m1", model_version="1")
    bundle = save_trained_model(tmp_path, model)
    man = build_manifest_from_bundle(
        bundle,
        status="candidate",
        hardware_profile="BALANCED",
        n_samples=len(y),
        oos_metrics={"accuracy": 0.6},
    )
    ok, reason = validate_manifest(man)
    assert ok, reason
    assert man.artifact_checksum
    assert man.feature_schema_hash
    assert man.dataset_fingerprint
    assert man.runtime_python
    path = save_manifest(tmp_path, man)
    assert path.is_file()
    loaded = load_manifest(tmp_path, "m1", "1")
    assert loaded is not None
    assert loaded.model_id == "m1"
    vok, vreason, _ = verify_manifest_against_disk(tmp_path, "m1", "1")
    assert vok, vreason


def test_manifest_checksum_mismatch(tmp_path: Path):
    X, y, names = _xy()
    model = train_baseline_classifier(X, y, feature_names=names, model_id="m2", model_version="1")
    bundle = save_trained_model(tmp_path, model)
    man = build_manifest_from_bundle(bundle, n_samples=len(y))
    save_manifest(tmp_path, man)
    art = list((tmp_path / "artifacts").rglob("model.pkl"))[0]
    art.write_bytes(art.read_bytes() + b"X")
    ok, reason, _ = verify_manifest_against_disk(tmp_path, "m2", "1")
    assert not ok
    assert reason == "checksum_mismatch"


def test_manifest_missing_fields():
    m = ArtifactManifest(model_id="x", model_version="1")
    ok, reason = validate_manifest(m)
    assert not ok


def test_safe_rollback_integrity_verified(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="old", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="new", model_version="2")
    reg.register_candidate(m1)
    reg.promote_champion("old", "1")
    reg.register_candidate(m2)
    reg.promote_champion("new", "2")
    assert verify_artifact_integrity(tmp_path, "old", "1").ok
    result = safe_rollback(reg, performance_collapse=True)
    assert result.success
    assert result.restored_id == "old"
    assert reg.champion().model_id == "old"


def test_safe_rollback_rejects_corrupt_previous(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    X, y, names = _xy()
    m1 = train_baseline_classifier(X, y, feature_names=names, model_id="old", model_version="1")
    m2 = train_baseline_classifier(X, y, feature_names=names, model_id="new", model_version="2")
    reg.register_candidate(m1)
    reg.promote_champion("old", "1")
    reg.register_candidate(m2)
    reg.promote_champion("new", "2")
    for art in (tmp_path / "artifacts").rglob("model.pkl"):
        if "old@1" in str(art):
            art.write_bytes(b"corrupt")
            break
    result = safe_rollback(reg, abnormal_drift=True)
    if not result.success:
        assert "integrity" in result.reason or "load_failed" in result.reason or "checksum" in result.reason


def test_safe_rollback_no_trigger(tmp_path: Path):
    reg = ModelRegistry(tmp_path)
    r = safe_rollback(reg)
    assert not r.success
    assert r.reason == "no_rollback_trigger"


def test_feature_schema_hash_stable():
    h1 = feature_schema_hash(["a", "b"], "v1")
    h2 = feature_schema_hash(["a", "b"], "v1")
    h3 = feature_schema_hash(["a", "c"], "v1")
    assert h1 == h2
    assert h1 != h3


def test_hardening_live_safety():
    from god.ml.adaptive import AdaptiveMLOrchestrator

    s = AdaptiveMLOrchestrator().safety_assertions()
    assert s["live_authorized"] is False
    assert s["broker_orders_submitted"] == 0
