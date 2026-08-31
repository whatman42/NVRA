"""Hardware capability models — diagnostic / resource only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class HardwareProfile(Enum):
    ULTRA_LITE = auto()
    LITE = auto()
    BALANCED = auto()
    PERFORMANCE = auto()
    HEAVY = auto()
    EXTREME = auto()


class StorageKind(Enum):
    HDD = auto()
    SSD = auto()
    NVME = auto()
    REMOVABLE = auto()
    UNKNOWN = auto()


class GpuVendor(Enum):
    NVIDIA = auto()
    AMD = auto()
    INTEL = auto()
    UNKNOWN = auto()
    NONE = auto()


@dataclass(frozen=True, slots=True)
class CpuInfo:
    vendor: str
    model: str
    architecture: str
    physical_cores: int | None
    logical_processors: int
    max_frequency_mhz: float | None
    flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RamInfo:
    total_bytes: int
    available_bytes: int | None

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024**3)

    @property
    def available_gb(self) -> float | None:
        if self.available_bytes is None:
            return None
        return self.available_bytes / (1024**3)


@dataclass(frozen=True, slots=True)
class GpuInfo:
    available: bool
    vendor: GpuVendor
    model: str
    vram_bytes: int | None
    dedicated: bool | None = None

    @property
    def vram_gb(self) -> float | None:
        if self.vram_bytes is None:
            return None
        return self.vram_bytes / (1024**3)


@dataclass(frozen=True, slots=True)
class StorageInfo:
    path: str
    filesystem: str
    total_bytes: int | None
    free_bytes: int | None
    kind: StorageKind
    removable: bool | None


@dataclass(frozen=True, slots=True)
class PowerInfo:
    on_battery: bool | None
    battery_percent: float | None
    power_saver: bool | None


@dataclass(frozen=True, slots=True)
class ThermalInfo:
    cpu_celsius: float | None
    gpu_celsius: float | None


@dataclass(frozen=True, slots=True)
class CapabilityScores:
    """Normalized 0..100 component scores. GPU does not auto-push EXTREME."""

    cpu: float
    ram: float
    storage: float
    gpu: float  # informational; not required for high profiles
    overall: float  # weighted without forcing GPU


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    """Computational budgets only — NEVER risk limits."""

    recommended_workers: int
    max_workers: int
    max_ml_models: int
    max_universe: int
    max_candidates: int
    max_ml_candidates: int
    max_predictions_per_cycle: int
    max_opportunities: int
    prediction_cache_size: int
    feature_cache_size: int
    market_cache_size: int
    ohlcv_cache_size: int
    max_features: int
    max_training_rows: int
    memory_pressure_warning_bytes: int
    memory_pressure_critical_bytes: int
    ml_profile_name: str  # maps to MLProfile name


@dataclass(frozen=True, slots=True)
class HardwareSnapshot:
    """Non-secret hardware snapshot for persistence and GUI/Telegram later."""

    timestamp_ms: int
    os_name: str
    os_version: str
    hostname: str
    virtualized: bool | None  # None = unknown
    cpu: CpuInfo
    ram: RamInfo
    gpu: GpuInfo
    storage: StorageInfo
    power: PowerInfo
    thermal: ThermalInfo
    scores: CapabilityScores
    profile: HardwareProfile
    budget: ResourceBudget
    reassess_required: bool = False
    previous_profile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "hostname": self.hostname,
            "virtualized": self.virtualized,
            "cpu": {
                "vendor": self.cpu.vendor,
                "model": self.cpu.model,
                "architecture": self.cpu.architecture,
                "physical_cores": self.cpu.physical_cores,
                "logical_processors": self.cpu.logical_processors,
                "max_frequency_mhz": self.cpu.max_frequency_mhz,
            },
            "ram": {
                "total_bytes": self.ram.total_bytes,
                "available_bytes": self.ram.available_bytes,
            },
            "gpu": {
                "available": self.gpu.available,
                "vendor": self.gpu.vendor.name,
                "model": self.gpu.model,
                "vram_bytes": self.gpu.vram_bytes,
            },
            "storage": {
                "path": self.storage.path,
                "filesystem": self.storage.filesystem,
                "total_bytes": self.storage.total_bytes,
                "free_bytes": self.storage.free_bytes,
                "kind": self.storage.kind.name,
                "removable": self.storage.removable,
            },
            "power": {
                "on_battery": self.power.on_battery,
                "battery_percent": self.power.battery_percent,
                "power_saver": self.power.power_saver,
            },
            "thermal": {
                "cpu_celsius": self.thermal.cpu_celsius,
                "gpu_celsius": self.thermal.gpu_celsius,
            },
            "scores": {
                "cpu": self.scores.cpu,
                "ram": self.scores.ram,
                "storage": self.scores.storage,
                "gpu": self.scores.gpu,
                "overall": self.scores.overall,
            },
            "profile": self.profile.name,
            "budget": {
                "recommended_workers": self.budget.recommended_workers,
                "max_workers": self.budget.max_workers,
                "max_ml_models": self.budget.max_ml_models,
                "max_universe": self.budget.max_universe,
                "max_candidates": self.budget.max_candidates,
                "max_ml_candidates": self.budget.max_ml_candidates,
                "max_predictions_per_cycle": self.budget.max_predictions_per_cycle,
                "max_opportunities": self.budget.max_opportunities,
                "prediction_cache_size": self.budget.prediction_cache_size,
                "feature_cache_size": self.budget.feature_cache_size,
                "market_cache_size": self.budget.market_cache_size,
                "ohlcv_cache_size": self.budget.ohlcv_cache_size,
                "max_features": self.budget.max_features,
                "max_training_rows": self.budget.max_training_rows,
                "memory_pressure_warning_bytes": self.budget.memory_pressure_warning_bytes,
                "memory_pressure_critical_bytes": self.budget.memory_pressure_critical_bytes,
                "ml_profile_name": self.budget.ml_profile_name,
            },
            "reassess_required": self.reassess_required,
            "previous_profile": self.previous_profile,
        }

    def summary_lines(self) -> list[str]:
        """Telegram/GUI-friendly summary (no secrets)."""
        gpu = self.gpu.model if self.gpu.available else "None"
        return [
            f"CPU: {self.cpu.model or self.cpu.vendor} ({self.cpu.logical_processors} threads)",
            f"RAM: {self.ram.total_gb:.1f} GB",
            f"Storage: {self.storage.kind.name}",
            f"GPU: {gpu}",
            f"Profile: {self.profile.name}",
            f"Workers: {self.budget.recommended_workers}",
            f"ML models: {self.budget.max_ml_models}",
            f"Candidate budget: {self.budget.max_ml_candidates}",
        ]
