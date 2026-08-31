"""Deterministic hardware profile classification and resource budgets."""

from __future__ import annotations

from crypto.hardware.models import (
    CapabilityScores,
    CpuInfo,
    GpuInfo,
    HardwareProfile,
    RamInfo,
    ResourceBudget,
    StorageInfo,
    StorageKind,
)


def score_cpu(cpu: CpuInfo) -> float:
    """0..100 based on logical processors (capability-based, not model names)."""
    n = max(1, cpu.logical_processors)
    # 1 → ~10, 2 → ~25, 4 → ~45, 8 → ~70, 16+ → ~95
    if n <= 1:
        return 12.0
    if n == 2:
        return 28.0
    if n <= 4:
        return 45.0
    if n <= 8:
        return 70.0
    if n <= 16:
        return 88.0
    return 96.0


def score_ram(ram: RamInfo) -> float:
    gb = ram.total_gb
    if gb < 1.5:
        return 8.0
    if gb < 2.5:
        return 18.0
    if gb < 4.5:
        return 35.0
    if gb < 8.5:
        return 55.0
    if gb < 16.5:
        return 72.0
    if gb < 32.5:
        return 88.0
    return 96.0


def score_storage(storage: StorageInfo) -> float:
    if storage.kind is StorageKind.NVME:
        return 90.0
    if storage.kind is StorageKind.SSD:
        return 75.0
    if storage.kind is StorageKind.REMOVABLE:
        return 20.0
    if storage.kind is StorageKind.HDD:
        return 30.0
    # UNKNOWN — mild penalty (could be slow USB)
    if storage.removable is True:
        return 22.0
    return 50.0


def score_gpu(gpu: GpuInfo) -> float:
    if not gpu.available:
        return 0.0
    base = 40.0
    if gpu.vram_bytes is not None:
        gb = gpu.vram_bytes / (1024**3)
        if gb >= 8:
            base = 85.0
        elif gb >= 4:
            base = 70.0
        elif gb >= 2:
            base = 55.0
    return base


def compute_scores(
    cpu: CpuInfo, ram: RamInfo, storage: StorageInfo, gpu: GpuInfo
) -> CapabilityScores:
    c = score_cpu(cpu)
    r = score_ram(ram)
    s = score_storage(storage)
    g = score_gpu(gpu)
    # Overall: CPU 40%, RAM 40%, Storage 20%. GPU separate — does not dominate.
    overall = 0.40 * c + 0.40 * r + 0.20 * s
    return CapabilityScores(cpu=c, ram=r, storage=s, gpu=g, overall=overall)


def classify_profile(
    scores: CapabilityScores, *, logical_cpus: int, ram_gb: float
) -> HardwareProfile:
    """Deterministic thresholds. Prefer capability score + hard floors."""
    o = scores.overall
    # Hard floors for ultra-low end
    if ram_gb <= 2.5 and logical_cpus <= 2:
        return HardwareProfile.ULTRA_LITE
    if o < 25 or (ram_gb < 3.5 and logical_cpus <= 2):
        return HardwareProfile.ULTRA_LITE
    if o < 40 or ram_gb < 4.5:
        return HardwareProfile.LITE
    if o < 58:
        return HardwareProfile.BALANCED
    if o < 75:
        return HardwareProfile.PERFORMANCE
    if o < 88:
        return HardwareProfile.HEAVY
    return HardwareProfile.EXTREME


def budget_for(profile: HardwareProfile, ram: RamInfo) -> ResourceBudget:
    """Resource budgets only — NEVER risk policy values."""
    total = max(ram.total_bytes, 512 * 1024 * 1024)
    warn = int(total * 0.75)
    crit = int(total * 0.90)

    table: dict[HardwareProfile, ResourceBudget] = {
        HardwareProfile.ULTRA_LITE: ResourceBudget(
            recommended_workers=1,
            max_workers=1,
            max_ml_models=1,
            max_universe=200,
            max_candidates=40,
            max_ml_candidates=15,
            max_predictions_per_cycle=8,
            max_opportunities=3,
            prediction_cache_size=16,
            feature_cache_size=32,
            market_cache_size=64,
            ohlcv_cache_size=32,
            max_features=20,
            max_training_rows=2_000,
            memory_pressure_warning_bytes=warn,
            memory_pressure_critical_bytes=crit,
            ml_profile_name="ULTRA_LITE",
        ),
        HardwareProfile.LITE: ResourceBudget(
            recommended_workers=1,
            max_workers=2,
            max_ml_models=2,
            max_universe=400,
            max_candidates=80,
            max_ml_candidates=30,
            max_predictions_per_cycle=12,
            max_opportunities=5,
            prediction_cache_size=32,
            feature_cache_size=64,
            market_cache_size=128,
            ohlcv_cache_size=64,
            max_features=30,
            max_training_rows=5_000,
            memory_pressure_warning_bytes=warn,
            memory_pressure_critical_bytes=crit,
            ml_profile_name="LITE",
        ),
        HardwareProfile.BALANCED: ResourceBudget(
            recommended_workers=2,
            max_workers=4,
            max_ml_models=3,
            max_universe=800,
            max_candidates=150,
            max_ml_candidates=50,
            max_predictions_per_cycle=20,
            max_opportunities=10,
            prediction_cache_size=64,
            feature_cache_size=128,
            market_cache_size=256,
            ohlcv_cache_size=128,
            max_features=40,
            max_training_rows=20_000,
            memory_pressure_warning_bytes=warn,
            memory_pressure_critical_bytes=crit,
            ml_profile_name="BALANCED",
        ),
        HardwareProfile.PERFORMANCE: ResourceBudget(
            recommended_workers=4,
            max_workers=8,
            max_ml_models=4,
            max_universe=1500,
            max_candidates=250,
            max_ml_candidates=80,
            max_predictions_per_cycle=40,
            max_opportunities=15,
            prediction_cache_size=128,
            feature_cache_size=256,
            market_cache_size=512,
            ohlcv_cache_size=256,
            max_features=40,
            max_training_rows=50_000,
            memory_pressure_warning_bytes=warn,
            memory_pressure_critical_bytes=crit,
            ml_profile_name="PERFORMANCE",
        ),
        HardwareProfile.HEAVY: ResourceBudget(
            recommended_workers=6,
            max_workers=12,
            max_ml_models=4,
            max_universe=2500,
            max_candidates=400,
            max_ml_candidates=120,
            max_predictions_per_cycle=60,
            max_opportunities=20,
            prediction_cache_size=256,
            feature_cache_size=512,
            market_cache_size=1024,
            ohlcv_cache_size=512,
            max_features=40,
            max_training_rows=80_000,
            memory_pressure_warning_bytes=warn,
            memory_pressure_critical_bytes=crit,
            ml_profile_name="PERFORMANCE",
        ),
        HardwareProfile.EXTREME: ResourceBudget(
            recommended_workers=8,
            max_workers=16,
            max_ml_models=4,
            max_universe=3000,
            max_candidates=500,
            max_ml_candidates=150,
            max_predictions_per_cycle=80,
            max_opportunities=25,
            prediction_cache_size=512,
            feature_cache_size=1024,
            market_cache_size=2048,
            ohlcv_cache_size=1024,
            max_features=40,
            max_training_rows=100_000,
            memory_pressure_warning_bytes=warn,
            memory_pressure_critical_bytes=crit,
            ml_profile_name="EXTREME",
        ),
    }
    return table[profile]
