"""ML Ensemble (Phase 7) — aggregation only, no orders."""

from importlib import import_module

__all__ = [
    "EnsembleEngine", "EnsemblePrediction", "aggregate_votes", "WeightConfig",
    "DEFAULT_WEIGHTS", "compute_weights",
]

_EXPORTS = {
    "EnsembleEngine": ("crypto.ensemble.engine", "EnsembleEngine"),
    "EnsemblePrediction": ("crypto.ensemble.aggregate", "EnsemblePrediction"),
    "aggregate_votes": ("crypto.ensemble.aggregate", "aggregate_votes"),
    "WeightConfig": ("crypto.ensemble.weighting", "WeightConfig"),
    "DEFAULT_WEIGHTS": ("crypto.ensemble.weighting", "DEFAULT_WEIGHTS"),
    "compute_weights": ("crypto.ensemble.weighting", "compute_weights"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
