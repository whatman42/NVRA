"""Optional compute providers — selection, fallback, security, validation (no cloud/GPU required)."""
from __future__ import annotations

from pathlib import Path

import pytest

from god.ml.compute import (
    ColabComputeProvider,
    ComputeConfig,
    JobStatus,
    KaggleComputeProvider,
    LocalComputeProvider,
    ProviderStatus,
    TrainingJob,
    WorkloadType,
    assert_no_execution_commands,
    assert_no_secrets,
    load_compute_config,
    sanitize_mapping,
    select_provider,
    validate_training_result,
)
from god.ml.registry import ModelRegistry, ModelRecord


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


def test_auto_prefers_enabled_available_colab_for_heavy():
    cfg = ComputeConfig(provider="auto")
    cfg.colab.enabled = True
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    heavy = TrainingJob(model_id="m", workload_type=WorkloadType.HEAVY.value)
    p = select_provider(cfg, colab=colab, job=heavy)
    assert p.name == "colab"


def test_light_workload_always_local_even_if_colab_available():
    cfg = ComputeConfig(provider="auto")
    cfg.colab.enabled = True
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    light = TrainingJob(model_id="m", workload_type=WorkloadType.LIGHT.value)
    p = select_provider(cfg, colab=colab, job=light)
    assert p.name == "local"


def test_inference_workload_always_local():
    cfg = ComputeConfig(provider="colab")
    cfg.colab.enabled = True
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    inf = TrainingJob(model_id="m", workload_type=WorkloadType.INFERENCE.value)
    p = select_provider(cfg, colab=colab, job=inf)
    assert p.name == "local"


def test_colab_rejects_non_heavy_workload():
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    job = TrainingJob(model_id="m", workload_type=WorkloadType.LIGHT.value)
    result = colab.submit(job, {"rows": 10})
    assert result.job.status == JobStatus.REJECTED
    assert "non_heavy" in result.job.metadata.get("reason", "")


def test_colab_disconnect_is_interrupted_not_success():
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    colab._force_disconnect = True
    job = TrainingJob(model_id="m1", dataset_hash="abc", workload_type=WorkloadType.HEAVY.value)
    result = colab.submit(job, {"dataset_id": "ds1"})
    assert result.job.status == JobStatus.INTERRUPTED
    assert result.job.status != JobStatus.SUCCESS


def test_kaggle_disconnect_is_interrupted_not_success():
    kaggle = KaggleComputeProvider(enabled=True)
    kaggle._force_status = ProviderStatus.AVAILABLE
    kaggle._force_disconnect = True
    result = kaggle.submit(TrainingJob(model_id="m1", workload_type=WorkloadType.HEAVY.value))
    assert result.job.status == JobStatus.INTERRUPTED


def test_local_submit_success_and_artifact(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    job = TrainingJob(model_id="baseline", dataset_hash="deadbeef", training_config_hash="cfg1")
    result = local.submit(job, {"rows": 100})
    assert result.job.status == JobStatus.SUCCESS
    assert result.artifact_hash
    assert Path(result.job.metadata["artifact_path"]).is_file()


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


def test_sanitize_nested_list_tuple_set():
    dirty = {
        "metadata": [{"api_token": "SECRET", "keep": 1}],
        "items": ({"broker_password": "SECRET"}, {"safe": 1}),
        "deep": [{"b": ({"mt5_login": "SECRET", "n": 2},)}],
        "tags": {"ok", "token_value_should_stay_as_value"},
    }
    clean = sanitize_mapping(dirty)
    assert "api_token" not in clean["metadata"][0]
    assert clean["metadata"][0]["keep"] == 1
    assert "broker_password" not in clean["items"][0]
    assert clean["items"][1]["safe"] == 1
    assert "mt5_login" not in clean["deep"][0]["b"][0]
    assert clean["deep"][0]["b"][0]["n"] == 2
    with pytest.raises(ValueError):
        assert_no_secrets({"metadata": [{"API_TOKEN": "x"}]})


def test_execution_command_injection_rejected():
    with pytest.raises(ValueError, match="execution command"):
        assert_no_execution_commands({"place_order": {"symbol": "EURUSD"}})
    with pytest.raises(ValueError, match="execution command"):
        assert_no_execution_commands({"nested": {"submit_order": 1}})
    with pytest.raises(ValueError, match="execution command"):
        assert_no_execution_commands({"bypass_governor": True})


def test_colab_rejects_execution_command_payload():
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    job = TrainingJob(model_id="m", workload_type=WorkloadType.HEAVY.value)
    result = colab.submit(job, {"place_order": {"lots": 1}})
    assert result.job.status == JobStatus.REJECTED
    assert "execution" in result.job.metadata.get("reason", "").lower() or "rejected_execution" in result.provider_notes


def test_job_manifest_rejects_secrets_on_submit(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    job = TrainingJob(model_id="m", metadata={"note": "ok"})
    result = local.submit(job, {"api_token": "secret", "feature": 1})
    assert result.job.status == JobStatus.SUCCESS
    assert "api_token" not in result.job.metadata


def test_tenant_id_propagates_to_local_artifact(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    job = TrainingJob(model_id="m", tenant_id="tenant-A", dataset_hash="h1")
    result = local.submit(job, {"rows": 5})
    assert result.job.status == JobStatus.SUCCESS
    assert result.job.metadata.get("tenant_id") == "tenant-A"
    assert result.job.provenance.get("tenant_id") == "tenant-A"


def test_job_contract_roundtrip():
    job = TrainingJob(
        tenant_id="t1",
        model_id="m",
        workload_type=WorkloadType.HEAVY.value,
        dataset_hash="abc",
        timeout_sec=120,
        requested_resources={"gpu": 1},
        provenance={"src": "unit"},
    )
    d = job.to_dict()
    back = TrainingJob.from_dict(d)
    assert back.tenant_id == "t1"
    assert back.workload_type == WorkloadType.HEAVY.value
    assert back.timeout_sec == 120
    assert back.requested_resources.get("gpu") == 1
    assert back.is_heavy()


def test_dataset_provenance_matching_pass(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    result = local.submit(TrainingJob(model_id="m", model_version="1", dataset_hash="ABC"))
    v = validate_training_result(result, expected_dataset_hash="ABC")
    assert v.ok and v.eligible_for_promotion


def test_dataset_provenance_wrong_hash_reject(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    result = local.submit(TrainingJob(model_id="m", dataset_hash="XYZ"))
    v = validate_training_result(result, expected_dataset_hash="ABC")
    assert not v.ok
    assert "dataset_hash_mismatch" in v.reasons


def test_dataset_provenance_missing_hash_reject(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    result = local.submit(TrainingJob(model_id="m", dataset_hash=""))
    v = validate_training_result(result, expected_dataset_hash="ABC")
    assert not v.ok
    assert "missing_dataset_hash" in v.reasons


def test_artifact_integrity_matching_pass(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    result = local.submit(TrainingJob(model_id="m", dataset_hash="h1"))
    path = result.job.metadata["artifact_path"]
    v = validate_training_result(result, expected_dataset_hash="h1", artifact_path=path)
    assert v.ok


def test_artifact_integrity_modified_file_reject(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    result = local.submit(TrainingJob(model_id="m", dataset_hash="h1"))
    path = Path(result.job.metadata["artifact_path"])
    path.write_bytes(path.read_bytes() + b"tamper")
    v = validate_training_result(result, expected_dataset_hash="h1", artifact_path=path)
    assert not v.ok
    assert "artifact_hash_mismatch" in v.reasons


def test_artifact_integrity_wrong_hash_reject(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    result = local.submit(TrainingJob(model_id="m", dataset_hash="h1"))
    result.artifact_hash = "0" * 64
    v = validate_training_result(
        result,
        expected_dataset_hash="h1",
        artifact_path=result.job.metadata["artifact_path"],
    )
    assert not v.ok
    assert "artifact_hash_mismatch" in v.reasons


def test_artifact_unresolvable_reject():
    local = LocalComputeProvider()  # no artifact_dir → local:// ref only
    result = local.submit(TrainingJob(model_id="m", dataset_hash="h1"))
    v = validate_training_result(result, expected_dataset_hash="h1")
    assert not v.ok
    assert "artifact_unresolvable" in v.reasons


def test_artifact_bytes_integrity(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    result = local.submit(TrainingJob(model_id="m", dataset_hash="h1"))
    raw = Path(result.job.metadata["artifact_path"]).read_bytes()
    v = validate_training_result(
        result, expected_dataset_hash="h1", artifact_bytes=raw, require_resolvable_artifact=False
    )
    assert v.ok
    v2 = validate_training_result(
        result, expected_dataset_hash="h1", artifact_bytes=b"nope", require_resolvable_artifact=False
    )
    assert not v2.ok


def test_failure_states_reject_promotion():
    for status, notes in [
        (JobStatus.INTERRUPTED, ("interrupted", "not_success")),
        (JobStatus.UNKNOWN, ()),
        (JobStatus.FAILED, ()),
        (JobStatus.REJECTED, ()),
    ]:
        colab = ColabComputeProvider(enabled=True)
        colab._force_status = ProviderStatus.AVAILABLE
        if status == JobStatus.INTERRUPTED:
            colab._force_disconnect = True
            result = colab.submit(
                TrainingJob(model_id="m", dataset_hash="h", workload_type=WorkloadType.HEAVY.value)
            )
        else:
            result = colab.submit(
                TrainingJob(model_id="m", dataset_hash="h", workload_type=WorkloadType.HEAVY.value)
            )
            result.job.status = status
        v = validate_training_result(result, expected_dataset_hash="h", require_resolvable_artifact=False)
        assert not v.eligible_for_promotion


def test_validate_success_eligible(tmp_path: Path):
    local = LocalComputeProvider(artifact_dir=tmp_path)
    result = local.submit(TrainingJob(model_id="m", model_version="1", dataset_hash="h1"))
    v = validate_training_result(result, expected_dataset_hash="h1")
    assert v.ok and v.eligible_for_promotion


def test_registry_promotion_rejects_invalid_compute(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    reg._records.append(
        ModelRecord(model_id="m", model_version="1", status="candidate", features_version="f1", dataset_hash="h1")
    )
    reg._save()
    colab = ColabComputeProvider(enabled=True)
    colab._force_status = ProviderStatus.AVAILABLE
    colab._force_disconnect = True
    bad = colab.submit(
        TrainingJob(model_id="m", model_version="1", dataset_hash="h1", workload_type=WorkloadType.HEAVY.value)
    )
    with pytest.raises(PermissionError, match="compute_validation_rejected"):
        reg.promote_champion("m", "1", training_result=bad, expected_dataset_hash="h1")


def test_registry_promotion_requires_training_result_when_gated(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    reg._records.append(
        ModelRecord(model_id="m", model_version="1", status="candidate", features_version="f1", dataset_hash="h1")
    )
    reg._save()
    with pytest.raises(PermissionError, match="training_result_missing"):
        reg.promote_champion("m", "1", require_compute_gate=True)


def test_registry_promotion_accepts_valid_compute(tmp_path: Path):
    reg = ModelRegistry(tmp_path / "reg")
    reg._records.append(
        ModelRecord(model_id="m", model_version="1", status="candidate", features_version="f1", dataset_hash="h1")
    )
    reg._save()
    local = LocalComputeProvider(artifact_dir=tmp_path / "arts")
    result = local.submit(TrainingJob(model_id="m", model_version="1", dataset_hash="h1"))
    promoted = reg.promote_from_compute(result, expected_dataset_hash="h1")
    assert promoted.status == "champion"


def test_direct_promote_without_compute_still_works_for_non_compute(tmp_path: Path):
    """Legacy path: non-compute models can promote without training_result."""
    reg = ModelRegistry(tmp_path / "reg")
    reg._records.append(
        ModelRecord(model_id="legacy", model_version="1", status="candidate", features_version="f1", dataset_hash="legacy")
    )
    reg._save()
    rec = reg.promote_champion("legacy", "1")
    assert rec.status == "champion"


def test_cloud_providers_do_not_support_inference_path():
    assert ColabComputeProvider(enabled=True).probe().supports_inference is False
    assert KaggleComputeProvider(enabled=True).probe().supports_inference is False
    assert LocalComputeProvider().probe().supports_inference is False


def test_colab_disabled_probe():
    assert ColabComputeProvider(enabled=False).probe().status == ProviderStatus.DISABLED


def test_colab_cannot_place_orders():
    """Structural proof: Colab provider has no order/broker methods."""
    colab = ColabComputeProvider(enabled=True)
    for name in ("place_order", "submit_order", "execute_trade", "mt5_order"):
        assert not hasattr(colab, name)
