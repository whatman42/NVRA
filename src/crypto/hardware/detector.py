"""Safe, privilege-free hardware detection (stdlib-first)."""

from __future__ import annotations

import os
import platform
import shutil
import sys
import ctypes
from contextlib import suppress
from pathlib import Path

from crypto.hardware.models import (
    CpuInfo,
    GpuInfo,
    GpuVendor,
    PowerInfo,
    RamInfo,
    StorageInfo,
    StorageKind,
    ThermalInfo,
)


def detect_cpu() -> CpuInfo:
    arch = platform.machine() or "unknown"
    vendor = "unknown"
    model = platform.processor() or ""
    logical = os.cpu_count() or 1
    physical: int | None = None
    freq: float | None = None
    flags: tuple[str, ...] = ()

    # Linux /proc
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        try:
            text = cpuinfo.read_text(encoding="utf-8", errors="replace")
            vendors = []
            models = []
            physical_ids = set()
            for line in text.splitlines():
                if line.startswith("vendor_id") and ":" in line:
                    vendors.append(line.split(":", 1)[1].strip())
                elif line.startswith("model name") and ":" in line:
                    models.append(line.split(":", 1)[1].strip())
                elif line.startswith("physical id") and ":" in line:
                    physical_ids.add(line.split(":", 1)[1].strip())
                elif line.startswith("cpu cores") and ":" in line and physical is None:
                    with suppress(ValueError):
                        physical = int(line.split(":", 1)[1].strip())
                elif line.startswith("flags") and ":" in line and not flags:
                    flags = tuple(line.split(":", 1)[1].strip().split())
            if vendors:
                vendor = vendors[0]
            if models:
                model = models[0]
            if physical is None and physical_ids:
                # rough: cores per package * packages unknown — leave None
                pass
        except OSError:
            pass

    # Windows registry not required — use platform fallbacks
    if not model:
        model = platform.processor() or f"{arch}-cpu"
    if sys.platform == "win32" and vendor == "unknown":
        vendor = "windows"

    return CpuInfo(
        vendor=vendor,
        model=model or "unknown",
        architecture=arch,
        physical_cores=physical,
        logical_processors=max(1, logical),
        max_frequency_mhz=freq,
        flags=flags,
    )


def detect_ram() -> RamInfo:
    total = 0
    available: int | None = None

    # Linux
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            data: dict[str, int] = {}
            for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
                if ":" not in line:
                    continue
                key, rest = line.split(":", 1)
                parts = rest.strip().split()
                if parts:
                    with suppress(ValueError):
                        # values in kB
                        data[key] = int(parts[0]) * 1024
            total = data.get("MemTotal", 0)
            # MemAvailable preferred
            available = data.get("MemAvailable") or data.get("MemFree")
        except OSError:
            pass

    if total <= 0 and sys.platform == "win32":
        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        try:
            status = _MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                total = int(status.ullTotalPhys)
                available = int(status.ullAvailPhys)
        except (AttributeError, OSError):
            pass

    if total <= 0:
        # Unknown hardware must be treated conservatively.
        total = 2 * 1024**3

    return RamInfo(total_bytes=total, available_bytes=available)


def detect_gpu() -> GpuInfo:
    """Lightweight GPU presence detection — no CUDA/ML frameworks."""
    # NVIDIA via nvidia-smi (optional binary)
    nvidia = shutil.which("nvidia-smi")
    if nvidia:
        try:
            import subprocess

            proc = subprocess.run(  # noqa: S603
                [nvidia, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                line = proc.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in line.split(",")]
                name = parts[0] if parts else "NVIDIA GPU"
                vram = None
                if len(parts) > 1:
                    with suppress(ValueError):
                        vram = int(float(parts[1]) * 1024 * 1024)  # MiB → bytes
                return GpuInfo(
                    available=True,
                    vendor=GpuVendor.NVIDIA,
                    model=name,
                    vram_bytes=vram,
                    dedicated=True,
                )
        except (OSError, Exception):
            pass

    # Linux DRM / sysfs
    drm = Path("/sys/class/drm")
    if drm.is_dir():
        for card in drm.glob("card[0-9]"):
            # skip if only virtual
            uevent = card / "device" / "uevent"
            if uevent.is_file():
                try:
                    text = uevent.read_text(encoding="utf-8", errors="replace").lower()
                    vendor = GpuVendor.UNKNOWN
                    if "nvidia" in text:
                        vendor = GpuVendor.NVIDIA
                    elif "amd" in text or "ati" in text:
                        vendor = GpuVendor.AMD
                    elif "intel" in text:
                        vendor = GpuVendor.INTEL
                    return GpuInfo(
                        available=True,
                        vendor=vendor,
                        model=f"drm-{card.name}",
                        vram_bytes=None,
                        dedicated=None,
                    )
                except OSError:
                    continue

    return GpuInfo(
        available=False,
        vendor=GpuVendor.NONE,
        model="",
        vram_bytes=None,
        dedicated=None,
    )


def detect_storage(path: str | Path | None = None) -> StorageInfo:
    root = Path(path) if path else Path.cwd()
    try:
        root = root.resolve()
    except OSError:
        root = Path.cwd()

    total: int | None = None
    free: int | None = None
    try:
        usage = shutil.disk_usage(str(root))
        total = usage.total
        free = usage.free
    except OSError:
        pass

    fstype = "unknown"
    removable: bool | None = None
    kind = StorageKind.UNKNOWN

    # Linux mount info
    mounts = Path("/proc/mounts")
    if mounts.is_file():
        try:
            best = ""
            for line in mounts.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.split()
                if len(parts) < 3:
                    continue
                mnt, fs = parts[1], parts[2]
                if str(root).startswith(mnt) and len(mnt) >= len(best):
                    best = mnt
                    fstype = fs
            # rotational?
            # try find block device for best mount — heuristic only
        except OSError:
            pass

    # Heuristic removable: path under /media /mnt /run/media or common USB markers
    path_s = str(root).lower()
    if any(x in path_s for x in ("/media/", "/mnt/", "/run/media", "usb")):
        removable = True
        kind = StorageKind.REMOVABLE
    elif fstype in ("vfat", "exfat", "ntfs") and removable is None:
        # often USB on Linux but not always
        removable = None

    # rotational flag via sysfs if we can map device — skip heavy; leave UNKNOWN
    return StorageInfo(
        path=str(root),
        filesystem=fstype,
        total_bytes=total,
        free_bytes=free,
        kind=kind,
        removable=removable,
    )


def detect_power() -> PowerInfo:
    # Linux sysfs battery
    bat = Path("/sys/class/power_supply")
    if bat.is_dir():
        on_ac: bool | None = None
        pct: float | None = None
        for p in bat.iterdir():
            try:
                t = (p / "type").read_text(encoding="utf-8").strip().lower()
                if t == "mains":
                    online = (p / "online").read_text(encoding="utf-8").strip()
                    on_ac = online == "1"
                elif t == "battery":
                    cap = p / "capacity"
                    if cap.is_file():
                        pct = float(cap.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
        if on_ac is not None or pct is not None:
            return PowerInfo(
                on_battery=(not on_ac) if on_ac is not None else None,
                battery_percent=pct,
                power_saver=None,
            )
    if sys.platform == "win32":
        class _SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_ubyte),
                ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte),
                ("Reserved", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        try:
            status = _SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                pct = None if status.BatteryLifePercent == 255 else float(status.BatteryLifePercent)
                return PowerInfo(
                    on_battery=(status.ACLineStatus == 0),
                    battery_percent=pct,
                    power_saver=None,
                )
        except (AttributeError, OSError):
            pass
    return PowerInfo(on_battery=None, battery_percent=None, power_saver=None)


def detect_thermal() -> ThermalInfo:
    # Linux hwmon — best effort, optional
    cpu_t: float | None = None
    hwmon = Path("/sys/class/hwmon")
    if hwmon.is_dir():
        for d in hwmon.iterdir():
            try:
                for tf in d.glob("temp*_input"):
                    raw = int(tf.read_text(encoding="utf-8").strip())
                    # millidegree
                    c = raw / 1000.0
                    if 0 < c < 120:
                        cpu_t = c
                        break
                if cpu_t is not None:
                    break
            except (OSError, ValueError):
                continue
    return ThermalInfo(cpu_celsius=cpu_t, gpu_celsius=None)


def detect_virtualized() -> bool | None:
    # DMI / systemd-detect-virt style heuristics
    vendors = (
        Path("/sys/class/dmi/id/product_name"),
        Path("/sys/class/dmi/id/sys_vendor"),
    )
    markers = ("kvm", "qemu", "vmware", "virtualbox", "xen", "hyper-v", "bochs", "parallels")
    for p in vendors:
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="replace").lower()
                if any(m in text for m in markers):
                    return True
            except OSError:
                pass
    # Docker / container
    if Path("/.dockerenv").exists():
        return True
    cgroup = Path("/proc/1/cgroup")
    if cgroup.is_file():
        try:
            text = cgroup.read_text(encoding="utf-8", errors="replace")
            if "docker" in text or "kubepods" in text or "containerd" in text:
                return True
        except OSError:
            pass
    return None  # unknown rather than false
