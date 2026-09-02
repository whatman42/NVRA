"""Optional compute providers — selection, fallback, security, validation (no cloud/GPU required)."""
from __future__ import annotations

import pytest

from god.ml.compute import (
    ColabComputeProvider,
    ComputeConfig,
    JobStatus,
    KaggleComputeProvider,
    LocalComputeProvider,
    ProviderStatus,
    TrainingJob,
    assert_no_secrets,
    load_compute_config,
    sanitize_mapping,
    select_provider,
    validate_training_result,
)


def test_default_config_is_local_safe():
    cfg = load_compute_config(None)
    assert cfg.provider == "auto"
    assert cfg.local.enabled is True
    assert cfg.colab.enabled is False
    assert cfg.kaggle.enabled is False


def test_missing_compute_section_defaults_local():
    cfg = load_compute_config({"other": 1})
    assert cfg.colab.enabled is False
    p = select_provider(cfg)
    assert isinstance(p, LocalComputeProvider)


def test_select_local_mode():
    cfg = ComputeConfig(provider="local")
    p = select_provider(cfg)
    assert p.name == "local"
    assert p.probe().status == ProviderStatus.AVAILABLE


def test_colab_unavailable_falls_back_to_local():
    cfg = ComputeConfig(provider="colab")
    colab = ColabComputeProvider(enabled=True)
    # Outside Colab runtime → UNAVAILABLE
    assert colab.probe().status == ProviderStatus.UNAVAILABLE
    p = select_provider(cfg, colab=colab)
    assert isinstance(p, LocalComputeProvider)


def test_kaggle_unavailable_falls_back_to_local():
    cfg = ComputeConfig(provider="kaggle")
    kaggle = KaggleComputeProvider(enabled=True)
    assert kaggle.probe().status == ProviderStatus.UNAVAILABLE
    p = select_provider(cfg, kaggle=kaggle)
    assert isinstance(p, LocalComputeProvider)


def test_auto_with_cloud_disabled_uses_local():
    cfg = load_compute_config(
        {
            "compute": {
                "provider": "auto",
                "colab": {"enabled": False},
                "kaggle": {"enabled": False},
            }
        }
    )
    p = select_provider(cfg)
    assert p.name == "local"


def test_auto_prefers_enabled_available_colab():
    cfg = ComputeConfig(provider="auto")
    cfg.colab.enabled = True
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    p = select_provider(cfg, colab=colab)
    assert p.name == "colab"


def test_colab_disconnect_is_interrupted_not_success():
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    colab._force_disconnect = True
    job = TrainingJob(model_id="m1", dataset_hash="abc")
    result = colab.submit(job, {"dataset_id": "ds1"})
    assert result.job.status == JobStatus.INTERRUPTED
    assert result.job.status != JobStatus.SUCCESS


def test_kaggle_disconnect_is_interrupted_not_success():
    kaggle = KaggleComputeProvider(enabled=True)
    kaggle._force_status = ProviderStatus.AVAILABLE
    kaggle._force_disconnect = True
    result = kaggle.submit(TrainingJob(model_id="m1"))
    assert result.job.status == JobStatus.INTERRUPTED


def test_local_submit_success_and_artifact():
    local = LocalComputeProvider()
    job = TrainingJob(model_id="baseline", dataset_hash="deadbeef", training_config_hash="cfg1")
    result = local.submit(job, {"rows": 100})
    assert result.job.status == JobStatus.SUCCESS
    assert result.artifact_hash
    assert result.job.artifact_ref.startswith("local://")


def test_sanitize_strips_credentials():
    dirty = {
        "dataset_hash": "abc",
        "api_key": "SHOULD_NOT_LEAK",
        "broker_password": "x",
        "mt5_login": "123",
        "nested": {"exchange_secret": "y", "ok": 1},
    }
    clean = sanitize_mapping(dirty)
    assert "api_key" not in clean
    assert "broker_password" not in clean
    assert "mt5_login" not in clean
    assert "exchange_secret" not in clean["nested"]
    assert clean["nested"]["ok"] == 1
    assert clean["dataset_hash"] == "abc"
    with pytest.raises(ValueError):
        assert_no_secrets(dirty)


def test_job_manifest_rejects_secrets_on_submit():
    local = LocalComputeProvider()
    job = TrainingJob(model_id="m", metadata={"note": "ok"})
    # sanitize happens inside submit; forbidden keys stripped, not raised when only in payload
    result = local.submit(job, {"api_token": "secret", "feature": 1})
    assert result.job.status == JobStatus.SUCCESS
    # ensure secrets never stored on job metadata from payload
    assert "api_token" not in result.job.metadata


def test_validate_success_eligible():
    local = LocalComputeProvider()
    result = local.submit(TrainingJob(model_id="m", dataset_hash="h1"))
    v = validate_training_result(result, expected_dataset_hash="h1")
    assert v.ok and v.eligible_for_promotion


def test_validate_interrupted_rejects_promotion():
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    colab._force_disconnect = True
    result = colab.submit(TrainingJob(model_id="m"))
    v = validate_training_result(result)
    assert not v.ok
    assert not v.eligible_for_promotion
    assert any("not_success" in r or "interrupted" in r for r in v.reasons)


def test_validate_bad_hash_rejects():
    local = LocalComputeProvider()
    result = local.submit(TrainingJob(model_id="m", dataset_hash="h1"))
    result.artifact_hash = "short"
    v = validate_training_result(result)
    assert not v.eligible_for_promotion


def test_cloud_providers_do_not_support_inference_path():
    assert ColabComputeProvider(enabled=True).probe().supports_inference is False
    assert KaggleComputeProvider(enabled=True).probe().supports_inference is False
    assert LocalComputeProvider().probe().supports_inference is False


def test_colab_disabled_probe():
    assert ColabComputeProvider(enabled=False).probe().status == ProviderStatus.DISABLED
