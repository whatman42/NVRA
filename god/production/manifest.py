"""Phase 6A — N.U.N.G. deployment manifest. Audit-safe, no secrets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from god.research.provenance import content_hash

from .config import ProductionConfig
from .fingerprint import configuration_fingerprint, configuration_id
from .validation import ConfigValidationResult, validate_config


@dataclass(frozen=True)
class DeploymentManifest:
    configuration_id: str
    configuration_hash: str
    environment: str
    app_name: str
    app_version: str
    config_version: str
    execution_mode: str
    data_source_id: str
    validation_status: str
    capabilities_enabled: tuple[str, ...]
    capabilities_disabled: tuple[str, ...]
    safety_gates: tuple[str, ...]
    content_hash: str
    schema_version: str = "deployment-manifest-6a-v1"
    notes: str = "no_secrets_in_manifest"

    def to_dict(self) -> dict[str, Any]:
        return {
            "configuration_id": self.configuration_id,
            "configuration_hash": self.configuration_hash,
            "environment": self.environment,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "config_version": self.config_version,
            "execution_mode": self.execution_mode,
            "data_source_id": self.data_source_id,
            "validation_status": self.validation_status,
            "capabilities_enabled": list(self.capabilities_enabled),
            "capabilities_disabled": list(self.capabilities_disabled),
            "safety_gates": list(self.safety_gates),
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "notes": self.notes,
        }


def build_manifest(
    config: ProductionConfig,
    validation: Optional[ConfigValidationResult] = None,
) -> DeploymentManifest:
    validation = validation or validate_config(config)
    flags = config.feature_flags.to_dict()
    enabled = tuple(k for k, v in flags.items() if v and k != "live_execution")
    disabled = tuple(k for k, v in flags.items() if not v) + ("live_execution",)
    safety = (
        "paper_only_default",
        "live_blocked_phase6a",
        "secret_refs_only",
        "fail_closed_validation",
    )
    cfg_hash = configuration_fingerprint(config)
    cid = configuration_id(config)
    payload = {
        "configuration_id": cid,
        "configuration_hash": cfg_hash,
        "environment": config.environment.value,
        "execution_mode": config.execution_mode.value,
        "validation_status": validation.status.value,
    }
    return DeploymentManifest(
        configuration_id=cid,
        configuration_hash=cfg_hash,
        environment=config.environment.value,
        app_name=config.app_name,
        app_version=config.app_version,
        config_version=config.config_version,
        execution_mode=config.execution_mode.value,
        data_source_id=config.data_source_id,
        validation_status=validation.status.value,
        capabilities_enabled=enabled,
        capabilities_disabled=disabled,
        safety_gates=safety,
        content_hash=content_hash(payload),
    )
