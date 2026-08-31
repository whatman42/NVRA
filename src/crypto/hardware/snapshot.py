"""Build and persist hardware snapshots; detect significant changes."""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path

from crypto.hardware.detector import (
    detect_cpu,
    detect_gpu,
    detect_power,
    detect_ram,
    detect_storage,
    detect_thermal,
    detect_virtualized,
)
from crypto.hardware.models import HardwareProfile, HardwareSnapshot
from crypto.hardware.profile import budget_for, classify_profile, compute_scores


def build_snapshot(
    *,
    storage_path: str | Path | None = None,
    previous: HardwareSnapshot | None = None,
) -> HardwareSnapshot:
    cpu = detect_cpu()
    ram = detect_ram()
    gpu = detect_gpu()
    storage = detect_storage(storage_path)
    power = detect_power()
    thermal = detect_thermal()
    scores = compute_scores(cpu, ram, storage, gpu)
    profile = classify_profile(scores, logical_cpus=cpu.logical_processors, ram_gb=ram.total_gb)
    budget = budget_for(profile, ram)

    reassess = False
    prev_name = None
    if previous is not None:
        prev_name = previous.profile.name
        reassess = significant_change(previous, cpu, ram, gpu, storage, profile)

    return HardwareSnapshot(
        timestamp_ms=int(time.time() * 1000),
        os_name=platform.system() or "unknown",
        os_version=platform.version() or "",
        hostname=platform.node() or "",
        virtualized=detect_virtualized(),
        cpu=cpu,
        ram=ram,
        gpu=gpu,
        storage=storage,
        power=power,
        thermal=thermal,
        scores=scores,
        profile=profile,
        budget=budget,
        reassess_required=reassess,
        previous_profile=prev_name,
    )


def significant_change(
    previous: HardwareSnapshot,
    cpu: object,
    ram: object,
    gpu: object,
    storage: object,
    new_profile: HardwareProfile,
) -> bool:
    """True if profile tier changed or RAM/CPU logical count shifted materially."""
    if previous.profile is not new_profile:
        return True
    # RAM change > 25%
    if previous.ram.total_bytes > 0:
        ratio = ram.total_bytes / previous.ram.total_bytes  # type: ignore[attr-defined]
        if ratio < 0.75 or ratio > 1.25:
            return True
    if cpu.logical_processors != previous.cpu.logical_processors:  # type: ignore[attr-defined]
        return True
    return bool(gpu.available) != bool(previous.gpu.available)  # type: ignore[attr-defined]


def save_snapshot(path: str | Path, snapshot: HardwareSnapshot) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = snapshot.to_dict()
    # Security: ensure no secret-like keys
    blob = json.dumps(data).lower()
    for bad in ("api_key", "api_secret", "password", "private_key", "token"):
        if bad in blob:
            raise ValueError("hardware snapshot must not contain secrets")
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_snapshot_dict(path: str | Path) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("snapshot must be a JSON object")
    return data
