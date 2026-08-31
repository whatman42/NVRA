"""Model family capability registry — optional deps, never required for startup.

Heavy ML (LSTM/GRU/Transformer) is modular and disabled on CONSERVATIVE.
Lightweight boosters (LightGBM/XGBoost) remain eligible on 8 GB when installed.
Champion selection remains validation-driven, not hardware-driven.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, asdict
from typing import Any, Optional

from .hardware import HardwareProfile, ResourceLimits


@dataclass(frozen=True)
class ModelFamilyCapability:
    family: str
    dependency_available: bool
    runtime_available: bool
    hardware_eligible: bool
    import_name: str
    min_profile: HardwareProfile
    is_heavy: bool = False
    memory_estimate_mb: int = 256
    cpu_requirement: int = 1
    gpu_required: bool = False
    gpu_available: bool = False
    training_allowed: bool = True
    inference_allowed: bool = True
    resource_priority: int = 50  # lower = preferred under pressure
    notes: str = ""

    @property
    def available(self) -> bool:
        """Backward-compatible aggregate."""
        return self.dependency_available and self.runtime_available

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["min_profile"] = self.min_profile.value
        d["available"] = self.available
        return d


def _spec_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def detect_model_capabilities(
    *,
    gpu_available: bool = False,
) -> dict[str, ModelFamilyCapability]:
    """Probe optional ML libraries without importing heavy packages when absent."""
    caps: dict[str, ModelFamilyCapability] = {}

    sklearn_ok = _spec_available("sklearn")
    caps["random_forest"] = ModelFamilyCapability(
        family="random_forest",
        dependency_available=True,
        runtime_available=True,
        hardware_eligible=True,
        import_name="sklearn.ensemble" if sklearn_ok else "numpy",
        min_profile=HardwareProfile.CONSERVATIVE,
        is_heavy=False,
        memory_estimate_mb=128,
        cpu_requirement=1,
        gpu_required=False,
        gpu_available=gpu_available,
        training_allowed=True,
        inference_allowed=True,
        resource_priority=10,
        notes="sklearn" if sklearn_ok else "numpy_logit_fallback",
    )
    caps["numpy_logit"] = ModelFamilyCapability(
        family="numpy_logit",
        dependency_available=True,
        runtime_available=True,
        hardware_eligible=True,
        import_name="numpy",
        min_profile=HardwareProfile.CONSERVATIVE,
        is_heavy=False,
        memory_estimate_mb=32,
        cpu_requirement=1,
        resource_priority=5,
        notes="always",
    )

    for family, mod, min_p, mem, prio in [
        ("lightgbm", "lightgbm", HardwareProfile.CONSERVATIVE, 256, 20),
        ("xgboost", "xgboost", HardwareProfile.CONSERVATIVE, 256, 25),
        ("catboost", "catboost", HardwareProfile.BALANCED, 384, 30),
    ]:
        ok = _spec_available(mod)
        caps[family] = ModelFamilyCapability(
            family=family,
            dependency_available=ok,
            runtime_available=ok,
            hardware_eligible=ok,
            import_name=mod,
            min_profile=min_p,
            is_heavy=False,
            memory_estimate_mb=mem,
            cpu_requirement=1,
            gpu_required=False,
            gpu_available=gpu_available,
            training_allowed=ok,
            inference_allowed=ok,
            resource_priority=prio,
            notes="installed" if ok else "optional_missing",
        )

    torch_ok = _spec_available("torch")
    for family in ("lstm", "gru", "transformer"):
        caps[family] = ModelFamilyCapability(
            family=family,
            dependency_available=torch_ok,
            runtime_available=torch_ok,
            hardware_eligible=torch_ok and gpu_available,
            import_name="torch",
            min_profile=HardwareProfile.HIGH_PERFORMANCE,
            is_heavy=True,
            memory_estimate_mb=768,
            cpu_requirement=2,
            gpu_required=True,
            gpu_available=gpu_available,
            # Heavy neural inference is permitted on 16GB+ hosts when torch exists.
            # Training remains GPU/high-memory gated by the ResourceGovernor.
            training_allowed=torch_ok and gpu_available,
            inference_allowed=torch_ok,
            resource_priority=90,
            notes=("torch_cpu_or_gpu_inference" if torch_ok else "heavy_optional_missing"),
        )

    return caps


def allowed_families_for_limits(
    limits: ResourceLimits,
    capabilities: Optional[dict[str, ModelFamilyCapability]] = None,
) -> list[str]:
    """Intersect governor allowance with actual installed capabilities."""
    caps = capabilities or detect_model_capabilities()
    out: list[str] = []
    profile_rank = {
        HardwareProfile.CONSERVATIVE: 0,
        HardwareProfile.BALANCED: 1,
        HardwareProfile.HIGH_PERFORMANCE: 2,
    }
    current = profile_rank[limits.profile]
    for name in limits.allowed_families:
        key = name.lower()
        cap = caps.get(key)
        if cap is None:
            continue
        if not cap.dependency_available or not cap.runtime_available:
            continue
        if cap.is_heavy and not limits.allow_heavy_ml:
            continue
        if profile_rank[cap.min_profile] > current:
            continue
        out.append(cap.family)
    if not out:
        out = ["numpy_logit"]
    # Deterministic order by resource_priority then name
    out.sort(key=lambda f: (caps[f].resource_priority if f in caps else 99, f))
    return out


class ModelCapabilityRegistry:
    """Queryable registry of what may run on this host."""

    def __init__(self, gpu_available: bool = False) -> None:
        self._gpu = gpu_available
        self._caps = detect_model_capabilities(gpu_available=gpu_available)

    def refresh(self, gpu_available: Optional[bool] = None) -> None:
        if gpu_available is not None:
            self._gpu = gpu_available
        self._caps = detect_model_capabilities(gpu_available=self._gpu)

    def get(self, family: str) -> Optional[ModelFamilyCapability]:
        return self._caps.get(family.lower())

    def all(self) -> dict[str, ModelFamilyCapability]:
        return dict(self._caps)

    def runnable(self, limits: ResourceLimits) -> list[str]:
        return allowed_families_for_limits(limits, self._caps)

    def inference_runnable(self, limits: ResourceLimits) -> list[str]:
        """Return models eligible for inference without enabling heavy training."""
        out = []
        rank = {
            HardwareProfile.CONSERVATIVE: 0,
            HardwareProfile.BALANCED: 1,
            HardwareProfile.HIGH_PERFORMANCE: 2,
        }
        current = rank[limits.profile]
        for name, cap in self._caps.items():
            if not cap.dependency_available or not cap.inference_allowed:
                continue
            if cap.is_heavy:
                if not limits.allow_heavy_ml_inference or current < rank[HardwareProfile.BALANCED]:
                    continue
            elif rank[cap.min_profile] > current:
                continue
            out.append(name)
        return sorted(out, key=lambda x: (self._caps[x].resource_priority, x))

    def to_dict(self) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in self._caps.items()}
