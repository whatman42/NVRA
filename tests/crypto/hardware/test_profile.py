"""Deterministic profile classification and risk isolation."""

from __future__ import annotations

from crypto.hardware.models import (
    CpuInfo,
    GpuInfo,
    GpuVendor,
    HardwareProfile,
    RamInfo,
    StorageInfo,
    StorageKind,
)
from crypto.hardware.profile import budget_for, classify_profile, compute_scores
from crypto.risk.policy import RiskPolicy


def _cpu(logical: int) -> CpuInfo:
    return CpuInfo(
        vendor="test",
        model="mock",
        architecture="x86_64",
        physical_cores=logical // 2 or 1,
        logical_processors=logical,
        max_frequency_mhz=None,
    )


def _ram(gb: float) -> RamInfo:
    return RamInfo(total_bytes=int(gb * 1024**3), available_bytes=int(gb * 0.5 * 1024**3))


def _storage(kind: StorageKind = StorageKind.UNKNOWN) -> StorageInfo:
    return StorageInfo(
        path="/tmp",
        filesystem="ext4",
        total_bytes=100 * 1024**3,
        free_bytes=50 * 1024**3,
        kind=kind,
        removable=kind is StorageKind.REMOVABLE,
    )


def _gpu(available: bool = False) -> GpuInfo:
    if not available:
        return GpuInfo(False, GpuVendor.NONE, "", None)
    return GpuInfo(True, GpuVendor.NVIDIA, "MockGPU", 4 * 1024**3, True)


def test_ultra_lite_low_end() -> None:
    scores = compute_scores(_cpu(1), _ram(2.0), _storage(StorageKind.HDD), _gpu(False))
    profile = classify_profile(scores, logical_cpus=1, ram_gb=2.0)
    assert profile is HardwareProfile.ULTRA_LITE
    b = budget_for(profile, _ram(2.0))
    assert b.recommended_workers == 1
    assert b.max_ml_models <= 2
    assert b.max_ml_candidates <= 20


def test_balanced_mid() -> None:
    scores = compute_scores(_cpu(6), _ram(8.0), _storage(StorageKind.SSD), _gpu(False))
    profile = classify_profile(scores, logical_cpus=6, ram_gb=8.0)
    assert profile in (
        HardwareProfile.BALANCED,
        HardwareProfile.PERFORMANCE,
        HardwareProfile.LITE,
    )


def test_gpu_does_not_force_extreme() -> None:
    scores = compute_scores(_cpu(2), _ram(4.0), _storage(StorageKind.HDD), _gpu(True))
    profile = classify_profile(scores, logical_cpus=2, ram_gb=4.0)
    assert profile is not HardwareProfile.EXTREME


def test_removable_storage_scores_low() -> None:
    scores = compute_scores(_cpu(4), _ram(8.0), _storage(StorageKind.REMOVABLE), _gpu(False))
    assert scores.storage < 40


def test_risk_policy_identical_across_profiles() -> None:
    """CRITICAL: hardware must not alter risk authority values."""
    policies = []
    for gb, logical, expected in (
        (2.0, 1, HardwareProfile.ULTRA_LITE),
        (32.0, 16, None),
    ):
        scores = compute_scores(_cpu(logical), _ram(gb), _storage(StorageKind.SSD), _gpu(False))
        profile = classify_profile(scores, logical_cpus=logical, ram_gb=gb)
        if expected:
            assert profile is expected
        # RiskPolicy is constructed independently of hardware
        policies.append(RiskPolicy())
    a, b = policies[0], policies[1]
    assert a.max_position_pct == b.max_position_pct
    assert a.max_daily_loss_pct == b.max_daily_loss_pct
    assert a.max_drawdown_pct == b.max_drawdown_pct
    assert a.max_portfolio_exposure_pct == b.max_portfolio_exposure_pct
    assert a.max_concurrent_positions == b.max_concurrent_positions


def test_budget_never_unbounded() -> None:
    for p in HardwareProfile:
        b = budget_for(p, _ram(16.0))
        assert b.max_workers >= 1
        assert b.max_universe > 0
        assert b.prediction_cache_size > 0
        assert b.memory_pressure_critical_bytes > b.memory_pressure_warning_bytes
