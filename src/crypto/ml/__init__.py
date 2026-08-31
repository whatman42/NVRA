"""Lightweight ML subsystem (Phase 6).

Produces predictions only. Never submits exchange orders.
"""

from crypto.ml.artifacts import ArtifactError, load_artifact, save_artifact
from crypto.ml.backends import available_algorithms
from crypto.ml.base import BaseModel, ModelMetadata
from crypto.ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from crypto.ml.governor import MLModelGovernor, MLSelection, ModelHealth
from crypto.ml.labels import LabelConfig
from crypto.ml.pipeline import MLPipeline, TrainResult
from crypto.ml.prediction import Direction, ModelVote, Prediction, Regime
from crypto.ml.profiles import DEFAULT_PROFILE, MLProfile, limits_for
from crypto.ml.provenance import (
    DataProvenance,
    LabeledRow,
    ProvenancePolicyError,
    assert_training_allowed,
    filter_for_training,
)
from crypto.ml.strategy import prediction_to_proposal

__all__ = [
    "MLPipeline",
    "TrainResult",
    "BaseModel",
    "ModelMetadata",
    "Prediction",
    "ModelVote",
    "Direction",
    "Regime",
    "LabelConfig",
    "MLProfile",
    "DEFAULT_PROFILE",
    "limits_for",
    "FEATURE_NAMES",
    "FEATURE_SCHEMA_VERSION",
    "available_algorithms",
    "save_artifact",
    "load_artifact",
    "ArtifactError",
    "prediction_to_proposal",
    "DataProvenance",
    "LabeledRow",
    "ProvenancePolicyError",
    "assert_training_allowed",
    "filter_for_training",
    "MLModelGovernor",
    "MLSelection",
    "ModelHealth",
]
