"""Map hardware budgets onto ML + scanner configs. Never touches RiskPolicy."""

from __future__ import annotations

from crypto.hardware.models import HardwareSnapshot, ResourceBudget
from crypto.ml.profiles import MLProfile
from crypto.scanner.config import ScannerConfig


def ml_profile_from_budget(budget: ResourceBudget) -> MLProfile:
    name = budget.ml_profile_name
    try:
        return MLProfile[name]
    except KeyError:
        return MLProfile.ULTRA_LITE


def scanner_config_from_budget(budget: ResourceBudget) -> ScannerConfig:
    return ScannerConfig(
        max_universe=budget.max_universe,
        max_candidates=budget.max_candidates,
        max_ml_candidates=budget.max_ml_candidates,
        max_predictions_per_cycle=budget.max_predictions_per_cycle,
        max_opportunities=budget.max_opportunities,
    )


def apply_snapshot_to_scanner_config(snapshot: HardwareSnapshot) -> ScannerConfig:
    return scanner_config_from_budget(snapshot.budget)


def apply_snapshot_to_ml_profile(snapshot: HardwareSnapshot) -> MLProfile:
    return ml_profile_from_budget(snapshot.budget)
