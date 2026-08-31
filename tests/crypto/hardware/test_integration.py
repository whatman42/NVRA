"""ML/scanner integration and snapshot helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from crypto.hardware import (
    HardwareProfile,
    apply_snapshot_to_ml_profile,
    apply_snapshot_to_scanner_config,
    build_snapshot,
    save_snapshot,
)
from crypto.hardware.models import (
    CpuInfo,
    GpuInfo,
    GpuVendor,
    RamInfo,
    StorageInfo,
    StorageKind,
)
from crypto.ml.profiles import MLProfile


def test_scanner_budget_mapping() -> None:
    with (
        patch("crypto.hardware.snapshot.detect_cpu") as dc,
        patch("crypto.hardware.snapshot.detect_ram") as dr,
        patch("crypto.hardware.snapshot.detect_gpu") as dg,
        patch("crypto.hardware.snapshot.detect_storage") as ds,
        patch("crypto.hardware.snapshot.detect_power") as dp,
        patch("crypto.hardware.snapshot.detect_thermal") as dt,
        patch("crypto.hardware.snapshot.detect_virtualized", return_value=False),
    ):
        dc.return_value = CpuInfo("t", "m", "x86_64", 1, 1, None)
        dr.return_value = RamInfo(2 * 1024**3, 1 * 1024**3)
        dg.return_value = GpuInfo(False, GpuVendor.NONE, "", None)
        ds.return_value = StorageInfo(
            "/data", "ext4", 100 * 1024**3, 50 * 1024**3, StorageKind.HDD, False
        )
        dp.return_value = type(
            "P", (), {"on_battery": None, "battery_percent": None, "power_saver": None}
        )()
        dt.return_value = type("T", (), {"cpu_celsius": None, "gpu_celsius": None})()
        # use real PowerInfo/ThermalInfo
        from crypto.hardware.models import PowerInfo, ThermalInfo

        dp.return_value = PowerInfo(None, None, None)
        dt.return_value = ThermalInfo(None, None)

        snap = build_snapshot()
        assert snap.profile is HardwareProfile.ULTRA_LITE
        cfg = apply_snapshot_to_scanner_config(snap)
        assert cfg.max_ml_candidates == snap.budget.max_ml_candidates
        ml = apply_snapshot_to_ml_profile(snap)
        assert ml is MLProfile.ULTRA_LITE


def test_save_snapshot_no_secrets(tmp_path: Path) -> None:
    with (
        patch("crypto.hardware.snapshot.detect_cpu") as dc,
        patch("crypto.hardware.snapshot.detect_ram") as dr,
        patch("crypto.hardware.snapshot.detect_gpu") as dg,
        patch("crypto.hardware.snapshot.detect_storage") as ds,
        patch("crypto.hardware.snapshot.detect_power") as dp,
        patch("crypto.hardware.snapshot.detect_thermal") as dt,
        patch("crypto.hardware.snapshot.detect_virtualized", return_value=None),
    ):
        from crypto.hardware.models import PowerInfo, ThermalInfo

        dc.return_value = CpuInfo("t", "m", "x86_64", 4, 4, None)
        dr.return_value = RamInfo(8 * 1024**3, 4 * 1024**3)
        dg.return_value = GpuInfo(False, GpuVendor.NONE, "", None)
        ds.return_value = StorageInfo(
            "/tmp", "ext4", 100 * 1024**3, 50 * 1024**3, StorageKind.SSD, False
        )
        dp.return_value = PowerInfo(None, None, None)
        dt.return_value = ThermalInfo(None, None)
        snap = build_snapshot()
        path = tmp_path / "hw.json"
        save_snapshot(path, snap)
        text = path.read_text(encoding="utf-8").lower()
        assert "api_key" not in text
        assert "secret" not in text
        assert "profile" in text


def test_summary_lines() -> None:
    with (
        patch("crypto.hardware.snapshot.detect_cpu") as dc,
        patch("crypto.hardware.snapshot.detect_ram") as dr,
        patch("crypto.hardware.snapshot.detect_gpu") as dg,
        patch("crypto.hardware.snapshot.detect_storage") as ds,
        patch("crypto.hardware.snapshot.detect_power") as dp,
        patch("crypto.hardware.snapshot.detect_thermal") as dt,
        patch("crypto.hardware.snapshot.detect_virtualized", return_value=False),
    ):
        from crypto.hardware.models import PowerInfo, ThermalInfo

        dc.return_value = CpuInfo("Intel", "i3", "x86_64", 2, 4, None)
        dr.return_value = RamInfo(4 * 1024**3, 2 * 1024**3)
        dg.return_value = GpuInfo(False, GpuVendor.NONE, "", None)
        ds.return_value = StorageInfo(
            "/", "ext4", 100 * 1024**3, 50 * 1024**3, StorageKind.HDD, False
        )
        dp.return_value = PowerInfo(None, None, None)
        dt.return_value = ThermalInfo(None, None)
        snap = build_snapshot()
        lines = snap.summary_lines()
        assert any("CPU" in x for x in lines)
        assert any("Profile" in x for x in lines)
