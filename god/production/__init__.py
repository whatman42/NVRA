"""Phase 6A — N.U.N.G. Production Configuration & Deployment Foundation.

LIVE execution is NOT authorized in this phase.
Configuration ≠ Execution Authority.
"""

from .config import (
    ExecutionMode,
    FeatureFlags,
    ProductionConfig,
    ResourceLimits,
    default_paper_config,
)
from .environment import Environment, parse_environment
from .fingerprint import configuration_fingerprint, configuration_id
from .health import ProductionHealth, ProductionHealthState, assess_health
from .manifest import DeploymentManifest, build_manifest
from .secrets import SecretRef, SecretRegistry, SecretStatus
from .validation import ConfigValidationResult, ConfigValidationStatus, validate_config

__all__ = [
    "Environment",
    "parse_environment",
    "ExecutionMode",
    "FeatureFlags",
    "ProductionConfig",
    "ResourceLimits",
    "default_paper_config",
    "SecretRef",
    "SecretRegistry",
    "SecretStatus",
    "ConfigValidationResult",
    "ConfigValidationStatus",
    "validate_config",
    "configuration_fingerprint",
    "configuration_id",
    "DeploymentManifest",
    "build_manifest",
    "ProductionHealth",
    "ProductionHealthState",
    "assess_health",
]
