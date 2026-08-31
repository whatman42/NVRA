"""Hardware-aware ML capability detector and resource governor.

Detects CPU/RAM/GPU/disk and selects CONSERVATIVE | BALANCED | HIGH_PERFORMANCE.
Never fails startup if GPU or heavy ML deps are missing.
Inference is always prioritized over training.

Profile policy (zero manual config):
  CONSERVATIVE: RAM <= 8 GB or high pressure
  BALANCED:     RAM 12–16 GB (16 GB is NEVER auto HIGH_PERFORMANCE)
  HIGH_PERFORMANCE: RAM >= 32 GB AND strong CPU AND low pressure
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional

try:
    import psutil

    _PSUTIL = True
except Exception:  # pragma: no cover
    psutil = None  # type: ignore
    _PSUTIL = False


class HardwareProfile(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    HIGH_PERFORMANCE = "HIGH_PERFORMANCE"


@dataclass(frozen=True)
class HardwareSnapshot:
    """Immutable snapshot of host resources at detection time."""

    cpu_cores: int = 1
    cpu_threads: int = 1
    total_ram_mb: int = 0
    available_ram_mb: int = 0
    gpu_available: bool = False
    vram_mb: int = 0
    gpu_vendor: str = ""
    gpu_name: str = ""
    available_disk_mb: int = 0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    platform: str = field(default_factory=lambda: platform.system())
    architecture: str = field(default_factory=lambda: platform.machine())
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResourceLimits:
    """Hard limits derived from profile + current pressure."""

    profile: HardwareProfile
    max_workers: int = 1
    max_parallel_train_jobs: int = 1
    max_ensemble_size: int = 1
    allow_ensemble: bool = False
    allow_heavy_ml: bool = False  # heavy ML training gate
    allow_heavy_ml_inference: bool = False  # heavy inference gate; independent of training
    allowed_families: tuple[str, ...] = ("random_forest", "numpy_logit")
    memory_budget_mb: int = 512
    inference_priority: bool = True
    sequential_training: bool = True
    training_allowed: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["profile"] = self.profile.value
        return d


def _detect_gpu() -> tuple[bool, int, str, str, tuple[str, ...]]:
    """Best-effort GPU detection without heavy dependencies.

    Returns (available, vram_mb, vendor, name, notes).
    Never raises.
    """
    notes: list[str] = []
    vendor = ""
    name = ""
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            import subprocess

            proc = subprocess.run(
                [
                    smi,
                    "--query-gpu=memory.total,name",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
                vram = 0
                for line in lines:
                    parts = [p.strip() for p in line.split(",")]
                    try:
                        vram = max(vram, int(float(parts[0])))
                    except (ValueError, IndexError):
                        continue
                    if len(parts) > 1 and not name:
                        name = parts[1]
                vendor = "nvidia"
                notes.append("nvidia-smi")
                return True, vram, vendor, name, tuple(notes)
        except Exception as e:
            notes.append(f"nvidia-smi_failed:{type(e).__name__}")
    try:
        import importlib.util

        if importlib.util.find_spec("torch") is not None:
            import torch  # type: ignore

            if torch.cuda.is_available():
                vram = 0
                try:
                    props = torch.cuda.get_device_properties(0)
                    vram = int(getattr(props, "total_memory", 0) // (1024 * 1024))
                    name = str(getattr(props, "name", "") or "")
                except Exception:
                    pass
                vendor = "nvidia"
                notes.append("torch.cuda")
                return True, vram, vendor, name, tuple(notes)
    except Exception:
        notes.append("torch_unavailable")
    return False, 0, "", "", tuple(notes or ("no_gpu",))


def detect_hardware() -> HardwareSnapshot:
    """Runtime hardware detection. Never fails startup."""
    notes: list[str] = []
    cores = os.cpu_count() or 1
    threads = cores
    total_ram = 0
    avail_ram = 0
    cpu_pct = 0.0
    mem_pct = 0.0
    disk_free = 0

    if _PSUTIL:
        try:
            threads = psutil.cpu_count(logical=True) or cores
            cores = psutil.cpu_count(logical=False) or cores
            vm = psutil.virtual_memory()
            total_ram = int(vm.total // (1024 * 1024))
            avail_ram = int(vm.available // (1024 * 1024))
            mem_pct = float(vm.percent)
            cpu_pct = float(psutil.cpu_percent(interval=0.05))
        except Exception as e:
            notes.append(f"psutil_partial:{type(e).__name__}")
    else:
        notes.append("psutil_missing")
        if platform.system() == "Linux":
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            total_ram = int(line.split()[1]) // 1024
                        elif line.startswith("MemAvailable:"):
                            avail_ram = int(line.split()[1]) // 1024
            except Exception:
                pass

    try:
        usage = shutil.disk_usage(os.path.abspath(os.sep))
        disk_free = int(usage.free // (1024 * 1024))
    except Exception:
        try:
            usage = shutil.disk_usage(".")
            disk_free = int(usage.free // (1024 * 1024))
        except Exception:
            notes.append("disk_unknown")

    gpu_ok, vram, vendor, gname, gpu_notes = _detect_gpu()
    notes.extend(gpu_notes)

    return HardwareSnapshot(
        cpu_cores=max(1, int(cores)),
        cpu_threads=max(1, int(threads)),
        total_ram_mb=max(0, total_ram),
        available_ram_mb=max(0, avail_ram),
        gpu_available=bool(gpu_ok),
        vram_mb=max(0, int(vram)),
        gpu_vendor=vendor,
        gpu_name=gname,
        available_disk_mb=max(0, disk_free),
        cpu_percent=float(cpu_pct),
        memory_percent=float(mem_pct),
        platform=platform.system(),
        architecture=platform.machine(),
        notes=tuple(notes),
    )


def select_profile(snapshot: Optional[HardwareSnapshot] = None) -> HardwareProfile:
    """Choose profile from capacity + current pressure.

    Policy (explicit):
      - RAM <= 8 GB              → CONSERVATIVE
      - high pressure / low avail → CONSERVATIVE
      - RAM >= 32 GB + >= 12 threads + low pressure → HIGH_PERFORMANCE
      - RAM 12–16 GB (incl. 16 GB) → BALANCED  (16 GB is NEVER HIGH_PERFORMANCE)
      - unknown total             → CONSERVATIVE
    """
    snap = snapshot or detect_hardware()
    total = snap.total_ram_mb
    avail = snap.available_ram_mb
    pressure = snap.memory_percent >= 75.0 or snap.cpu_percent >= 85.0

    if total > 0 and total <= 8192:
        return HardwareProfile.CONSERVATIVE
    if pressure and (avail > 0 and avail < 2048):
        return HardwareProfile.CONSERVATIVE
    # HIGH_PERFORMANCE requires >= 32 GB — 16 GB must stay BALANCED
    if total >= 32768 and snap.cpu_threads >= 12 and not pressure:
        return HardwareProfile.HIGH_PERFORMANCE
    if total >= 12288:
        return HardwareProfile.BALANCED
    if total == 0:
        return HardwareProfile.CONSERVATIVE
    # 8–12 GB band without pressure → still conservative-leaning BALANCED floor
    return HardwareProfile.BALANCED if total > 8192 else HardwareProfile.CONSERVATIVE


def build_resource_limits(
    snapshot: Optional[HardwareSnapshot] = None,
    profile: Optional[HardwareProfile] = None,
) -> ResourceLimits:
    """Derive execution limits. Resource Governor output.

    CONSERVATIVE (8 GB):
      RF + numpy_logit always; lightweight LightGBM/XGBoost when deps present
      and pressure low. No neural. Sequential. Small ensemble only if pressure
      allows (default off).
    BALANCED (12–16 GB):
      RF + LGB + XGB + CatBoost; limited ensemble; no neural.
    HIGH_PERFORMANCE (>= 32 GB + strong CPU):
      all tree models + neural if GPU/VRAM available.
    """
    snap = snapshot or detect_hardware()
    prof = profile or select_profile(snap)

    pressure = snap.memory_percent >= 70.0 or snap.cpu_percent >= 80.0

    if prof == HardwareProfile.CONSERVATIVE:
        workers = 1
        parallel = 1
        ensemble = False
        ensemble_size = 1
        heavy = False
        heavy_inference = False
        # 8 GB: RF + lightweight boosters (not neural)
        families = ("random_forest", "numpy_logit", "lightgbm", "xgboost")
        budget = min(768, max(256, snap.available_ram_mb // 8 if snap.available_ram_mb else 512))
        sequential = True
        training_ok = not (snap.memory_percent >= 85.0 or (snap.available_ram_mb and snap.available_ram_mb < 512))
    elif prof == HardwareProfile.BALANCED:
        workers = min(2, max(1, snap.cpu_threads // 2))
        parallel = 1 if pressure else min(2, workers)
        ensemble = not pressure
        ensemble_size = 1 if pressure else 3
        heavy = False
        heavy_inference = bool(snap.available_ram_mb >= 4096 and not pressure)
        families = ("random_forest", "numpy_logit", "lightgbm", "xgboost", "catboost")
        budget = min(2048, max(512, snap.available_ram_mb // 4 if snap.available_ram_mb else 1024))
        sequential = pressure
        training_ok = not (snap.memory_percent >= 85.0)
    else:  # HIGH_PERFORMANCE
        workers = min(4, max(2, snap.cpu_threads // 2))
        parallel = 1 if pressure else min(3, workers)
        ensemble = True
        ensemble_size = 2 if pressure else 5
        heavy = bool(snap.gpu_available) and snap.vram_mb >= 4096 and not pressure
        heavy_inference = True
        families = (
            "random_forest",
            "numpy_logit",
            "lightgbm",
            "xgboost",
            "catboost",
        )
        if heavy:
            families = families + ("lstm", "gru", "transformer")
        budget = min(8192, max(1024, snap.available_ram_mb // 3 if snap.available_ram_mb else 2048))
        sequential = pressure
        training_ok = True

    if pressure:
        workers = 1
        parallel = 1
        sequential = True
        ensemble_size = min(ensemble_size, 1)
        if ensemble_size <= 1:
            ensemble = False
        heavy_inference = False

    return ResourceLimits(
        profile=prof,
        max_workers=max(1, workers),
        max_parallel_train_jobs=max(1, parallel),
        max_ensemble_size=max(1, ensemble_size),
        allow_ensemble=ensemble,
        allow_heavy_ml=heavy,
        allow_heavy_ml_inference=heavy_inference,
        allowed_families=families,
        memory_budget_mb=max(128, budget),
        inference_priority=True,
        sequential_training=sequential,
        training_allowed=training_ok,
    )


class ResourceGovernor:
    """Stateful governor: re-evaluates under pressure; never changes champion."""

    def __init__(self, snapshot: Optional[HardwareSnapshot] = None) -> None:
        self._snapshot = snapshot or detect_hardware()
        self._profile = select_profile(self._snapshot)
        self._limits = build_resource_limits(self._snapshot, self._profile)
        self._training_active = False

    @property
    def snapshot(self) -> HardwareSnapshot:
        return self._snapshot

    @property
    def profile(self) -> HardwareProfile:
        return self._profile

    @property
    def limits(self) -> ResourceLimits:
        return self._limits

    def refresh(self) -> ResourceLimits:
        """Re-detect pressure and tighten limits if needed."""
        self._snapshot = detect_hardware()
        base = select_profile(self._snapshot)
        if self._snapshot.memory_percent >= 80.0 or self._snapshot.available_ram_mb < 1024:
            self._profile = HardwareProfile.CONSERVATIVE
        else:
            self._profile = base
        self._limits = build_resource_limits(self._snapshot, self._profile)
        return self._limits

    def may_start_training(self) -> bool:
        """Inference priority: refuse training under severe pressure."""
        if not self._limits.training_allowed:
            return False
        if self._training_active and self._limits.max_parallel_train_jobs <= 1:
            return False
        snap = detect_hardware()
        if snap.memory_percent >= 85.0 or (snap.available_ram_mb and snap.available_ram_mb < 512):
            return False
        return True

    def begin_training(self) -> bool:
        if not self.may_start_training():
            return False
        self._training_active = True
        return True

    def end_training(self) -> None:
        self._training_active = False

    def family_allowed(self, family: str) -> bool:
        return family.lower() in {f.lower() for f in self._limits.allowed_families}

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self._snapshot.to_dict(),
            "profile": self._profile.value,
            "limits": self._limits.to_dict(),
            "training_active": self._training_active,
        }
