"""Linux-safe diagnostic tests (mock, not real Windows verification)."""

from __future__ import annotations

from god.bridge.windows.diagnostic import WindowsDiagnostic


def test_diagnostic_linux_reports_windows_unavailable():
    d = WindowsDiagnostic(system="Linux")
    report = d.run()
    assert report.is_windows is False
    assert report.os_name == "Linux"
    assert any("WINDOWS_UNAVAILABLE" in n for n in report.notes)
    assert "password" not in str(report.to_dict()).lower()
    assert "gh_pat" not in str(report.to_dict()).lower()


def test_diagnostic_mock_windows_with_injected_terminals():
    class T:
        terminal_id = "t1"
        platform = "MT5"
        executable_path = r"D:\MT5\terminal64.exe"
        data_path = r"D:\MT5"
        experts_path = r"D:\MT5\MQL5\Experts"
        status = "DISCOVERED"

    d = WindowsDiagnostic(
        system="Windows",
        which=lambda c: "C:\\Windows\\System32\\where.exe" if c.startswith("where") else None,
        terminal_discover=lambda: [T()],
        registry_available=True,
        localhost_check=lambda: True,
    )
    report = d.run()
    assert report.is_windows is True
    assert report.registry_available is True
    assert len(report.terminal_candidates) == 1
    assert report.terminal_candidates[0]["terminal_id"] == "t1"


def test_diagnostic_redacted_to_dict():
    report = WindowsDiagnostic(system="Linux").run()
    d = report.to_dict()
    assert "python_version" in d
    assert isinstance(d["path_entries"], int)
