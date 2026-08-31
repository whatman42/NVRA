from pathlib import Path

from god.gui import autostart


def test_autostart_marker_roundtrip(tmp_path: Path):
    assert not autostart.is_disabled_by_user(tmp_path)
    autostart.mark_disabled(tmp_path)
    assert autostart.is_disabled_by_user(tmp_path)
    autostart.clear_disabled_marker(tmp_path)
    assert not autostart.is_disabled_by_user(tmp_path)


def test_autostart_is_safe_noop_off_windows(tmp_path: Path):
    if autostart.is_supported():
        return
    assert autostart.enable() is False
    assert autostart.disable() is False
    assert autostart.is_enabled() is False
