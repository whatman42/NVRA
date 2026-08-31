"""Final Gate 2 — broker abstraction & live readiness (fail-closed).

DETECTION ≠ AUTHORIZATION · DEMO ≠ LIVE · Gate PASS ≠ automatic trading

Broker and MT5 implementation modules are exposed lazily so importing the
abstraction package does not initialise optional broker adapters.
"""

from importlib import import_module
from typing import Any

# Preserve the package's existing public export list (the final __all__ in the
# baseline) while also retaining compatibility for previously accessible
# attributes through __getattr__.
__all__ = [
    "BrokerMode",
    "BrokerModePolicy",
    "BrokerModeRouter",
    "BrokerSession",
    "REAL_CONFIRMATION",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "AccountState": ("god.broker.models", "AccountState"),
    "AccountType": ("god.broker.models", "AccountType"),
    "LiveReadinessState": ("god.broker.models", "LiveReadinessState"),
    "ProviderHealth": ("god.broker.models", "ProviderHealth"),
    "BrokerExecutionProvider": ("god.broker.provider", "BrokerExecutionProvider"),
    "DemoBrokerProvider": ("god.broker.provider", "DemoBrokerProvider"),
    "LiveReadinessGate": ("god.broker.readiness", "LiveReadinessGate"),
    "ReadinessReport": ("god.broker.readiness", "ReadinessReport"),
    "MT5ExecutionAdapter": ("god.broker.mt5", "MT5ExecutionAdapter"),
    "MT5DemoGate": ("god.broker.mt5", "MT5DemoGate"),
    "MT5ConnectionConfig": ("god.broker.mt5", "MT5ConnectionConfig"),
    "BrokerMode": ("god.broker.modes", "BrokerMode"),
    "BrokerModePolicy": ("god.broker.modes", "BrokerModePolicy"),
    "REAL_CONFIRMATION": ("god.broker.modes", "REAL_CONFIRMATION"),
    "BrokerModeRouter": ("god.broker.router", "BrokerModeRouter"),
    "BrokerSession": ("god.broker.router", "BrokerSession"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    try:
        value = getattr(import_module(module_name), attribute)
    except ImportError:
        # Preserve the baseline fail-closed behaviour for optional MT5 support.
        if name in {"MT5ExecutionAdapter", "MT5DemoGate", "MT5ConnectionConfig"}:
            value = None
        else:
            raise
    globals()[name] = value
    return value
