from __future__ import annotations

from crypto.governor.states import GovernorState
from crypto.ml.base import ModelMetadata
from crypto.ml.governor import MLModelGovernor


def _meta(algorithm: str, accuracy: float) -> ModelMetadata:
    return ModelMetadata(
        model_id=f"{algorithm}-1",
        version="1",
        algorithm=algorithm,
        feature_schema_version="v1",
        feature_names=("f1",),
        training_rows=100,
        training_data_hash="x",
        metrics={"accuracy": accuracy, "test_accuracy": accuracy},
    )


def test_ultra_lite_uses_one_best_model() -> None:
    g = MLModelGovernor()
    models = [(object(), _meta("lightgbm", 0.70)), (object(), _meta("xgboost", 0.80))]
    r = g.select(models, profile_name="ULTRA_LITE", state=GovernorState.NORMAL)
    assert r.active_algorithms == ("xgboost",)
    assert set(r.rejected_algorithms) == {"lightgbm"}


def test_extreme_can_use_all_strong_models() -> None:
    g = MLModelGovernor()
    models = [
        (object(), _meta("lightgbm", 0.70)),
        (object(), _meta("xgboost", 0.71)),
        (object(), _meta("random_forest", 0.72)),
        (object(), _meta("catboost", 0.73)),
    ]
    r = g.select(models, profile_name="EXTREME", state=GovernorState.NORMAL)
    assert set(r.active_algorithms) == {"lightgbm", "xgboost", "random_forest", "catboost"}


def test_runtime_errors_demote_a_model() -> None:
    g = MLModelGovernor()
    for _ in range(8):
        g.observe("xgboost", latency_ms=3000, success=False)
    models = [
        (object(), _meta("lightgbm", 0.70)),
        (object(), _meta("xgboost", 0.95)),
    ]
    r = g.select(models, profile_name="BALANCED", state=GovernorState.NORMAL)
    assert "lightgbm" in r.active_algorithms
    assert "xgboost" not in r.active_algorithms


def test_critical_never_expands_model_slots() -> None:
    g = MLModelGovernor()
    models = [(object(), _meta("lightgbm", 0.70)), (object(), _meta("xgboost", 0.71))]
    r = g.select(models, profile_name="EXTREME", state=GovernorState.CRITICAL)
    assert len(r.active_algorithms) == 1
