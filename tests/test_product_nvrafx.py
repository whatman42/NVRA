"""Product packaging invariants: sole distributed binary is NVRA.exe.

NVRAFX.exe and NUNG.exe must not be product outputs.
Product: NVRA | Developer: NUNG (identity only — never default credential).
Adaptive ML and LIVE safety remain enforced.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from god.ml.hardware import (
    HardwareProfile,
    HardwareSnapshot,
    build_resource_limits,
    select_profile,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_nvrafx_entry():
    path = ROOT / "scripts" / "nvrafx_entry.py"
    spec = importlib.util.spec_from_file_location("nvrafx_entry", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nvrafx_entry"] = mod
    spec.loader.exec_module(mod)
    return mod


nvrafx_entry = _load_nvrafx_entry()


def _snap(total_ram_mb: int, **kw) -> HardwareSnapshot:
    defaults = dict(
        cpu_cores=4,
        cpu_threads=8,
        available_ram_mb=total_ram_mb // 2,
        gpu_available=False,
        vram_mb=0,
        available_disk_mb=50_000,
        cpu_percent=10.0,
        memory_percent=40.0,
        platform="Linux",
        architecture="x86_64",
        notes=("test",),
    )
    defaults.update(kw)
    return HardwareSnapshot(total_ram_mb=total_ram_mb, **defaults)


def test_product_name_is_nvra():
    assert nvrafx_entry.PRODUCT_NAME == "NVRA"
    assert nvrafx_entry.DEVELOPER_NAME == "NUNG"
    text = nvrafx_entry._version_text()
    assert "NVRA" in text
    assert "Developed by NUNG" in text
    assert "NVRA.exe" in text


def test_cli_version_health_check_config():
    assert nvrafx_entry.cmd_version() == 0
    assert nvrafx_entry.cmd_health() == 0
    code = nvrafx_entry.cmd_check_config()
    assert code in (0, 1)


def test_health_payload_safety():
    buf = io.StringIO()
    with redirect_stdout(buf):
        nvrafx_entry.cmd_health()
    data = json.loads(buf.getvalue())
    assert data["live_authorized"] is False
    assert data["broker_orders_submitted"] == 0
    assert data["product"] == "NVRA"
    assert data.get("developer") == "NUNG"
    assert data["executable"] == "NVRA.exe"


def test_packaging_specs_name_nvra_only():
    specs = [
        ROOT / "packaging" / "nvrafx_onefile.spec",
        ROOT / "packaging" / "nung_windows.spec",
        ROOT / "packaging" / "nvra_onefile.spec",
    ]
    for spec in specs:
        text = spec.read_text(encoding="utf-8")
        assert 'name="NVRA"' in text or "name='NVRA'" in text
        assert "name='NUNG'" not in text
        assert 'name="NUNG"' not in text
        assert "name='NVRAFX'" not in text
        assert 'name="NVRAFX"' not in text
        assert "console=False" in text or "console = False" in text


def test_workflows_reference_nvra_exe():
    wb = (ROOT / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")
    nv = (ROOT / ".github" / "workflows" / "nvra_windows_release.yml").read_text(encoding="utf-8")
    assert "NVRA.exe" in wb
    assert "NVRA.exe" in nv
    assert "NVRA.exe missing" in wb


def test_no_default_nung_credentials_in_entry():
    text = (ROOT / "scripts" / "nvrafx_entry.py").read_text(encoding="utf-8")
    lowered = text.lower()
    assert 'password = "nung"' not in lowered
    assert "DEFAULT_USERNAME" not in text


def test_main_version_health():
    assert nvrafx_entry.main(["--version"]) == 0
    assert nvrafx_entry.main(["--health"]) == 0


def test_adaptive_ml_8gb_not_rf_only():
    limits = build_resource_limits(_snap(8192))
    assert limits.profile == HardwareProfile.CONSERVATIVE
    assert "random_forest" in limits.allowed_families
    assert "lightgbm" in limits.allowed_families
    assert "xgboost" in limits.allowed_families
    assert "lstm" not in limits.allowed_families


def test_adaptive_ml_16gb_balanced():
    assert (
        select_profile(_snap(16384, cpu_threads=8, memory_percent=30.0))
        == HardwareProfile.BALANCED
    )


def test_adaptive_ml_32gb_high_performance():
    snap = _snap(
        32768,
        cpu_threads=16,
        memory_percent=25.0,
        gpu_available=True,
        vram_mb=8192,
    )
    assert select_profile(snap) == HardwareProfile.HIGH_PERFORMANCE
