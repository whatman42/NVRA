"""Optional multi-provider compute backends (Local / Colab / Kaggle).

Cloud providers are opportunistic accelerators for training/research only.
They never participate in signal, risk, execution, or SAFE_MODE paths.
"""
from .base import ComputeProvider
from .colab import ColabComputeProvider
from .config import ColabConfig, ComputeConfig, KaggleConfig, LocalConfig, load_compute_config
from .kaggle import KaggleComputeProvider
from .local import LocalComputeProvider
from .security import assert_no_secrets, sanitize_mapping
from .selector import select_provider
from .types import (
    JobStatus,
    ProviderCapability,
    ProviderStatus,
    TrainingJob,
    TrainingResult,
)
from .validation import ArtifactValidationResult, validate_training_result

__all__ = [
    "ComputeProvider",
    "LocalComputeProvider",
    "ColabComputeProvider",
    "KaggleComputeProvider",
    "select_provider",
    "ComputeConfig",
    "LocalConfig",
    "ColabConfig",
    "KaggleConfig",
    "load_compute_config",
    "TrainingJob",
    "TrainingResult",
    "JobStatus",
    "ProviderStatus",
    "ProviderCapability",
    "sanitize_mapping",
    "assert_no_secrets",
    "validate_training_result",
    "ArtifactValidationResult",
]
