"""Hardware detection and resource profiles (Phase 8).

Hardware NEVER modifies RiskPolicy or trading safety limits.

Public exports are resolved lazily so importing low-level hardware models does
not eagerly import scanner/ML integration modules.
"""

from importlib import import_module

__all__ = [
    "HardwareProfile", "HardwareSnapshot", "ResourceBudget", "CapabilityScores",
    "CpuInfo", "RamInfo", "GpuInfo", "GpuVendor", "StorageInfo", "StorageKind",
    "PowerInfo", "ThermalInfo", "build_snapshot", "save_snapshot", "load_snapshot_dict",
    "compute_scores", "classify_profile", "budget_for", "ml_profile_from_budget",
    "scanner_config_from_budget", "apply_snapshot_to_ml_profile",
    "apply_snapshot_to_scanner_config",
]

_EXPORTS = {
    "HardwareProfile": ("crypto.hardware.models", "HardwareProfile"),
    "HardwareSnapshot": ("crypto.hardware.models", "HardwareSnapshot"),
    "ResourceBudget": ("crypto.hardware.models", "ResourceBudget"),
    "CapabilityScores": ("crypto.hardware.models", "CapabilityScores"),
    "CpuInfo": ("crypto.hardware.models", "CpuInfo"),
    "RamInfo": ("crypto.hardware.models", "RamInfo"),
    "GpuInfo": ("crypto.hardware.models", "GpuInfo"),
    "GpuVendor": ("crypto.hardware.models", "GpuVendor"),
    "StorageInfo": ("crypto.hardware.models", "StorageInfo"),
    "StorageKind": ("crypto.hardware.models", "StorageKind"),
    "PowerInfo": ("crypto.hardware.models", "PowerInfo"),
    "ThermalInfo": ("crypto.hardware.models", "ThermalInfo"),
    "build_snapshot": ("crypto.hardware.snapshot", "build_snapshot"),
    "save_snapshot": ("crypto.hardware.snapshot", "save_snapshot"),
    "load_snapshot_dict": ("crypto.hardware.snapshot", "load_snapshot_dict"),
    "compute_scores": ("crypto.hardware.profile", "compute_scores"),
    "classify_profile": ("crypto.hardware.profile", "classify_profile"),
    "budget_for": ("crypto.hardware.profile", "budget_for"),
    "ml_profile_from_budget": ("crypto.hardware.integration", "ml_profile_from_budget"),
    "scanner_config_from_budget": ("crypto.hardware.integration", "scanner_config_from_budget"),
    "apply_snapshot_to_ml_profile": ("crypto.hardware.integration", "apply_snapshot_to_ml_profile"),
    "apply_snapshot_to_scanner_config": ("crypto.hardware.integration", "apply_snapshot_to_scanner_config"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
