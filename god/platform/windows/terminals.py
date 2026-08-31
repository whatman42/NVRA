"""Windows terminal path helpers — soft, never mandatory.

Used by TerminalDiscovery when running on Windows.
On non-Windows these are no-ops / return None.
"""

from __future__ import annotations

import os
import platform
from typing import Optional


def expand_path(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))


def registry_query_soft(key_path: str, value_name: str = "") -> Optional[str]:
    """Best-effort Windows Registry read. Returns None on failure / non-Windows."""
    if platform.system() != "Windows":
        return None
    try:
        import winreg  # type: ignore

        parts = key_path.split("\\", 1)
        if len(parts) != 2:
            return None
        root_name, sub = parts
        roots = {
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        }
        root = roots.get(root_name.upper())
        if root is None:
            return None
        with winreg.OpenKey(root, sub) as key:
            if value_name:
                val, _ = winreg.QueryValueEx(key, value_name)
            else:
                val, _ = winreg.QueryValueEx(key, "")
            return str(val) if val else None
    except Exception:
        return None
