"""AdaptiveModelSelector — deterministic, zero-manual-config model selection.

Selection is driven by:
  hardware capabilities + resource pressure + installed deps +
  governor limits + champion protection.

Never:
  - random selection
  - pick heaviest model just because hardware is strong
  - auto-swap champion without promotion gate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from .hardware import HardwareProfile, ResourceGovernor, ResourceLimits
from .model_capabilities import ModelCapabilityRegistry, ModelFamilyCapability, allowed_families_for_limits
from .registry import ModelRecord, ModelRegistry


@dataclass(frozen=True)
class SelectionResult:
    eligible: tuple[str, ...]
    selected: str
    ensemble_families: tuple[str, ...]
    worker_count: int
    max_ensemble_size: int
    training_budget_mb: int
    profile: HardwareProfile
    reason: str = ""
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": list(self.eligible),
            "selected": self.selected,
            "ensemble_families": list(self.ensemble_families),
            "worker_count": self.worker_count,
            "max_ensemble_size": self.max_ensemble_size,
            "training_budget_mb": self.training_budget_mb,
            "profile": self.profile.value,
            "reason": self.reason,
            "notes": list(self.notes),
        }


class AdaptiveModelSelector:
    """Deterministic selector for zero-config adaptive ML."""

    def __init__(
        self,
        governor: Optional[ResourceGovernor] = None,
        capabilities: Optional[ModelCapabilityRegistry] = None,
        registry: Optional[ModelRegistry] = None,
    ) -> None:
        self.governor = governor or ResourceGovernor()
        self.capabilities = capabilities or ModelCapabilityRegistry(
            gpu_available=self.governor.snapshot.gpu_available
        )
        self.registry = registry

    def select(
        self,
        *,
        candidate_families: Optional[Sequence[str]] = None,
        prefer_champion: bool = True,
    ) -> SelectionResult:
        limits = self.governor.limits
        caps = self.capabilities.all()
        eligible = allowed_families_for_limits(limits, caps)
        if candidate_families:
            allowed_set = {c.lower() for c in candidate_families}
            eligible = [e for e in eligible if e.lower() in allowed_set] or eligible

        notes: list[str] = []
        selected = eligible[0] if eligible else "numpy_logit"

        # Prefer existing champion family if still eligible (does not promote)
        if prefer_champion and self.registry is not None:
            champ = self.registry.champion()
            if champ is not None:
                fam = (champ.model_family or champ.model_id or "").lower()
                if fam in {e.lower() for e in eligible}:
                    selected = fam
                    notes.append("prefer_champion_family")
                else:
                    notes.append("champion_family_not_eligible_fallback")

        ensemble: list[str] = []
        if limits.allow_ensemble and limits.max_ensemble_size > 1:
            # Take up to max_ensemble_size by priority order already in eligible
            ensemble = list(eligible[: limits.max_ensemble_size])
            notes.append(f"ensemble_size={len(ensemble)}")
        else:
            ensemble = [selected]
            notes.append("sequential_or_single")

        reason = (
            f"profile={limits.profile.value};"
            f"eligible={len(eligible)};"
            f"selected={selected}"
        )
        return SelectionResult(
            eligible=tuple(eligible),
            selected=selected,
            ensemble_families=tuple(ensemble),
            worker_count=limits.max_workers,
            max_ensemble_size=limits.max_ensemble_size,
            training_budget_mb=limits.memory_budget_mb,
            profile=limits.profile,
            reason=reason,
            notes=tuple(notes),
        )

    def refresh_and_select(self) -> SelectionResult:
        self.governor.refresh()
        self.capabilities.refresh(gpu_available=self.governor.snapshot.gpu_available)
        return self.select()
