"""Asset-aware opportunity scanner (Phase 7)."""

from importlib import import_module

__all__ = [
    "OpportunityScanner", "ScannerConfig", "Opportunity", "ReasonCode",
    "Feasibility", "ScanTelemetry", "ReachableMarket", "build_reachable_universe",
    "opportunity_to_proposal", "ensemble_to_proposal",
]

_EXPORTS = {
    "OpportunityScanner": ("crypto.scanner.engine", "OpportunityScanner"),
    "ScannerConfig": ("crypto.scanner.config", "ScannerConfig"),
    "Opportunity": ("crypto.scanner.opportunity", "Opportunity"),
    "ReasonCode": ("crypto.scanner.opportunity", "ReasonCode"),
    "Feasibility": ("crypto.scanner.opportunity", "Feasibility"),
    "ScanTelemetry": ("crypto.scanner.opportunity", "ScanTelemetry"),
    "ReachableMarket": ("crypto.scanner.universe", "ReachableMarket"),
    "build_reachable_universe": ("crypto.scanner.universe", "build_reachable_universe"),
    "opportunity_to_proposal": ("crypto.scanner.strategy_bridge", "opportunity_to_proposal"),
    "ensemble_to_proposal": ("crypto.scanner.strategy_bridge", "ensemble_to_proposal"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
