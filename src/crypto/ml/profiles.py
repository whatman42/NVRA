"""ML resource profiles (explicit; hardware auto-detection is Phase 8/9)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class MLProfile(Enum):
    ULTRA_LITE = auto()
    LITE = auto()
    BALANCED = auto()
    PERFORMANCE = auto()
    EXTREME = auto()


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Hard bounds — no uncontrolled auto-scaling in Phase 6."""

    max_threads: int
    max_trees: int
    max_depth: int
    max_features: int
    max_training_rows: int
    algorithms: tuple[str, ...]  # ordered preference


_PROFILE_LIMITS: dict[MLProfile, ResourceLimits] = {
    MLProfile.ULTRA_LITE: ResourceLimits(
        max_threads=1,
        max_trees=20,
        max_depth=3,
        max_features=20,
        max_training_rows=2_000,
        algorithms=("lightgbm", "fallback"),
    ),
    MLProfile.LITE: ResourceLimits(
        max_threads=2,
        max_trees=50,
        max_depth=4,
        max_features=30,
        max_training_rows=5_000,
        algorithms=("lightgbm", "random_forest", "fallback"),
    ),
    MLProfile.BALANCED: ResourceLimits(
        max_threads=4,
        max_trees=100,
        max_depth=6,
        max_features=40,
        max_training_rows=20_000,
        algorithms=("lightgbm", "xgboost", "random_forest", "fallback"),
    ),
    MLProfile.PERFORMANCE: ResourceLimits(
        max_threads=8,
        max_trees=200,
        max_depth=8,
        max_features=40,
        max_training_rows=50_000,
        algorithms=("lightgbm", "xgboost", "random_forest", "catboost", "fallback"),
    ),
    MLProfile.EXTREME: ResourceLimits(
        max_threads=16,
        max_trees=400,
        max_depth=10,
        max_features=40,
        max_training_rows=100_000,
        algorithms=("lightgbm", "xgboost", "random_forest", "catboost", "fallback"),
    ),
}


def limits_for(profile: MLProfile) -> ResourceLimits:
    return _PROFILE_LIMITS[profile]


DEFAULT_PROFILE = MLProfile.ULTRA_LITE
