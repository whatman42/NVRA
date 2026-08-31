"""Dynamic Resource Governor (Phase 9).

Computational resource authority only.
Never modifies RiskPolicy or execution safety limits.

Public exports are resolved lazily to avoid importing the full governor
subsystem when a low-level state type is imported.
"""

from importlib import import_module

__all__ = [
    "ResourceGovernor",
    "GovernorState",
    "GovernorSnapshot",
    "GovernorEvent",
    "GovernorThresholds",
    "AdaptiveBudget",
    "scale_budget",
    "MarketDataFreshnessGate",
    "DataFreshness",
    "MemoryPressure",
    "RingStatus",
    "ResourceSample",
    "sample_resources",
]

_EXPORTS = {
    "ResourceGovernor": ("crypto.governor.engine", "ResourceGovernor"),
    "GovernorSnapshot": ("crypto.governor.engine", "GovernorSnapshot"),
    "GovernorEvent": ("crypto.governor.engine", "GovernorEvent"),
    "GovernorThresholds": ("crypto.governor.config", "GovernorThresholds"),
    "AdaptiveBudget": ("crypto.governor.budgets", "AdaptiveBudget"),
    "scale_budget": ("crypto.governor.budgets", "scale_budget"),
    "MarketDataFreshnessGate": ("crypto.governor.freshness", "MarketDataFreshnessGate"),
    "GovernorState": ("crypto.governor.states", "GovernorState"),
    "DataFreshness": ("crypto.governor.states", "DataFreshness"),
    "MemoryPressure": ("crypto.governor.states", "MemoryPressure"),
    "RingStatus": ("crypto.governor.states", "RingStatus"),
    "ResourceSample": ("crypto.governor.telemetry", "ResourceSample"),
    "sample_resources": ("crypto.governor.telemetry", "sample_resources"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
