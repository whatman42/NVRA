"""Phase 6A — N.U.N.G. production configuration model. LIVE not authorized."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .environment import Environment


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    LIVE = "LIVE"


SCHEMA_VERSION = "production-config-6a-v1"


@dataclass(frozen=True)
class ResourceLimits:
    max_symbols: int = 500
    max_bars: int = 5000
    max_paper_records: int = 500
    max_portfolio_history: int = 200
    max_audit_records: int = 1000

    def to_dict(self) -> dict[str, int]:
        return {
            "max_symbols": self.max_symbols,
            "max_bars": self.max_bars,
            "max_paper_records": self.max_paper_records,
            "max_portfolio_history": self.max_portfolio_history,
            "max_audit_records": self.max_audit_records,
        }


@dataclass(frozen=True)
class FeatureFlags:
    paper_pipeline: bool = True
    shadow_decision: bool = True
    readiness_gate: bool = True
    live_execution: bool = False  # always false in 6A defaults

    def to_dict(self) -> dict[str, bool]:
        return {
            "paper_pipeline": self.paper_pipeline,
            "shadow_decision": self.shadow_decision,
            "readiness_gate": self.readiness_gate,
            "live_execution": self.live_execution,
        }


@dataclass(frozen=True)
class ProductionConfig:
    environment: Environment
    app_name: str
    app_version: str
    config_version: str
    execution_mode: ExecutionMode
    data_source_id: str
    audit_enabled: bool
    resource_limits: ResourceLimits
    feature_flags: FeatureFlags
    schema_version: str = SCHEMA_VERSION
    deployment_id: str = "local"
    # secret references only — never raw values
    secret_refs: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        """Serializable view without secret values."""
        return {
            "environment": self.environment.value,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "config_version": self.config_version,
            "execution_mode": self.execution_mode.value,
            "data_source_id": self.data_source_id,
            "audit_enabled": self.audit_enabled,
            "resource_limits": self.resource_limits.to_dict(),
            "feature_flags": self.feature_flags.to_dict(),
            "schema_version": self.schema_version,
            "deployment_id": self.deployment_id,
            "secret_refs": list(self.secret_refs),
            # extra may not contain secrets by policy
            "extra": {k: v for k, v in self.extra.items() if "secret" not in k.lower() and "password" not in k.lower() and "token" not in k.lower()},
        }


def default_paper_config(
    *,
    environment: Environment = Environment.TEST,
    app_version: str = "0.6.0-phase6a",
) -> ProductionConfig:
    return ProductionConfig(
        environment=environment,
        app_name="N.U.N.G.",
        app_version=app_version,
        config_version="6a-1",
        execution_mode=ExecutionMode.PAPER,
        data_source_id="memory",
        audit_enabled=True,
        resource_limits=ResourceLimits(),
        feature_flags=FeatureFlags(live_execution=False),
        secret_refs=(),
    )
