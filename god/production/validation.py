"""Phase 6A — N.U.N.G. production config validation. Fail-closed."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import ExecutionMode, ProductionConfig, ResourceLimits
from .environment import Environment


class ConfigValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ConfigValidationResult:
    status: ConfigValidationStatus
    reasons: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.status == ConfigValidationStatus.VALID


def validate_config(config: Optional[ProductionConfig]) -> ConfigValidationResult:
    if config is None:
        return ConfigValidationResult(ConfigValidationStatus.UNKNOWN, ("missing_config",))

    reasons: list[str] = []

    if not isinstance(config.environment, Environment):
        reasons.append("invalid_environment")

    if not config.app_name or not str(config.app_name).strip():
        reasons.append("missing_app_name")
    if config.app_name and config.app_name != "N.U.N.G.":
        # identity must remain N.U.N.G.
        if "N.U.N.G" not in config.app_name:
            reasons.append("app_identity_mismatch")

    if not config.app_version:
        reasons.append("missing_app_version")
    if not config.config_version:
        reasons.append("missing_config_version")

    if not isinstance(config.execution_mode, ExecutionMode):
        reasons.append("invalid_execution_mode")

    # LIVE is never authorized in Phase 6A
    if config.execution_mode == ExecutionMode.LIVE:
        reasons.append("live_not_authorized_phase6a")
    if config.feature_flags.live_execution:
        reasons.append("live_feature_flag_blocked")

    if not config.data_source_id:
        reasons.append("missing_data_source_id")

    if not config.audit_enabled and config.environment == Environment.PRODUCTION:
        reasons.append("production_requires_audit")

    limits = config.resource_limits
    if not isinstance(limits, ResourceLimits):
        reasons.append("invalid_resource_limits")
    else:
        for name, val in limits.to_dict().items():
            if not isinstance(val, int) or val <= 0:
                reasons.append(f"invalid_limit_{name}")
            if val > 1_000_000:
                reasons.append(f"unsafe_limit_{name}")

    if reasons:
        # LIVE / blocked reasons dominate
        if any("live" in r for r in reasons):
            return ConfigValidationResult(ConfigValidationStatus.BLOCKED, tuple(reasons))
        return ConfigValidationResult(ConfigValidationStatus.INVALID, tuple(reasons))

    return ConfigValidationResult(ConfigValidationStatus.VALID, ())
