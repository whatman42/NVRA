"""MetaEditor discovery — mock probes, honest NOT_WINDOWS."""

from __future__ import annotations

from god.bridge.models import Platform, TerminalInstance
from god.bridge.windows.metaeditor import MetaEditorDiscovery, MetaEditorStatus


def test_not_windows():
    d = MetaEditorDiscovery(system="Linux")
    assert d.availability() == MetaEditorStatus.NOT_WINDOWS
    assert d.discover() == []


def test_not_found_on_windows_mock():
    d = MetaEditorDiscovery(system="Windows", which=lambda c: None, path_probe=lambda p: False)
    assert d.availability() == MetaEditorStatus.NOT_FOUND


def test_available_via_path_mock():
    d = MetaEditorDiscovery(
        system="Windows",
        which=lambda c: r"D:\MT5\metaeditor64.exe" if "metaeditor" in c.lower() else None,
        path_probe=lambda p: True,
    )
    assert d.availability() == MetaEditorStatus.AVAILABLE
    found = d.discover()
    assert len(found) >= 1


def test_find_for_terminal_sibling():
    d = MetaEditorDiscovery(
        system="Windows",
        which=lambda c: None,
        path_probe=lambda p: p.endswith("metaeditor64.exe"),
    )
    t = TerminalInstance.create(
        platform=Platform.MT5,
        executable_path=r"D:\MT5\terminal64.exe",
    )
    ed = d.find_for_terminal(t)
    assert ed is not None
    assert ed.provenance == "terminal_sibling"


def test_ambiguous_editors():
    paths = {
        "metaeditor64.exe": r"D:\A\metaeditor64.exe",
        "metaeditor.exe": r"D:\B\metaeditor.exe",
    }
    d = MetaEditorDiscovery(
        system="Windows",
        which=lambda c: paths.get(c.lower()) or paths.get(c),
        path_probe=lambda p: True,
    )
    status = d.availability()
    assert status in (MetaEditorStatus.AVAILABLE, MetaEditorStatus.AMBIGUOUS)
