"""Phase 0 foundation tests.

These tests verify only the minimal surface that Phase 0 exposes.
No exchange, ML, GUI, or execution behaviour is tested here.
"""

from __future__ import annotations

import crypto
from crypto.core import HardwareProfile, Severity
from crypto.core.types import HardwareProfile as HP
from crypto.core.types import Severity as Sev


def test_package_version() -> None:
    assert crypto.__version__ == "0.1.0"


def test_hardware_profile_members() -> None:
    expected = {
        "ULTRA_LITE",
        "LITE",
        "BALANCED",
        "PERFORMANCE",
        "HEAVY",
        "EXTREME",
    }
    actual = {p.name for p in HardwareProfile}
    assert actual == expected


def test_hardware_profile_is_enum() -> None:
    assert isinstance(HardwareProfile.ULTRA_LITE, HardwareProfile)
    assert HardwareProfile.BALANCED is HP.BALANCED


def test_severity_members() -> None:
    expected = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    actual = {s.name for s in Severity}
    assert actual == expected


def test_severity_is_enum() -> None:
    assert isinstance(Severity.INFO, Severity)
    assert Severity.CRITICAL is Sev.CRITICAL


def test_core_exports() -> None:
    """Ensure public surface of crypto.core is stable."""
    from crypto import core

    assert hasattr(core, "HardwareProfile")
    assert hasattr(core, "Severity")
