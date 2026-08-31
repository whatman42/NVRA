"""Windows per-user startup integration for NVRA.

Uses the standard HKCU Run key. Production command is headless autonomous:
  NVRA.exe --autostart --headless

NUNG is the developer/publisher identity only — never a default credential.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "NVRA"
RUN_KEY = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
AUTOSTART_ARGUMENT = "--autostart --headless"


def _command() -> str:
    executable = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        return f'"{executable}" {AUTOSTART_ARGUMENT}'
    entry = Path(sys.argv[0]).resolve()
    return f'"{executable}" "{entry}" {AUTOSTART_ARGUMENT}'


def _disabled_marker(data_dir: Path) -> Path:
    return Path(data_dir) / ".autostart.disabled"


def is_disabled_by_user(data_dir: Path) -> bool:
    return _disabled_marker(data_dir).exists()


def mark_disabled(data_dir: Path) -> None:
    marker = _disabled_marker(data_dir)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("disabled\n", encoding="utf-8")


def clear_disabled_marker(data_dir: Path) -> None:
    try:
        _disabled_marker(data_dir).unlink()
    except FileNotFoundError:
        pass


def is_supported() -> bool:
    return os.name == "nt"


def is_enabled() -> bool:
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return str(value).strip().lower() == _command().strip().lower()
    except (FileNotFoundError, OSError):
        return False


def enable() -> bool:
    if not is_supported():
        return False
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
    return True


def disable() -> bool:
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass
    return True
