"""Windows-only integration tests — skipped on Linux; never fake pass."""

from __future__ import annotations

import sys

import pytest


@pytest.mark.windows_integration
def test_real_windows_host_required():
    """REAL WINDOWS TEST REQUIRED — does not run on Linux CI."""
    if sys.platform != "win32":
        pytest.skip("REAL WINDOWS TEST REQUIRED: host is not win32")
    from god.bridge.windows.diagnostic import WindowsDiagnostic

    report = WindowsDiagnostic().run()
    assert report.is_windows is True
