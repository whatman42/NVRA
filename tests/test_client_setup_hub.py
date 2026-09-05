"""Client Setup Hub — presence of setup surfaces and login guard."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


def test_gui_source_has_client_setup_methods():
    """Static check so CI without PySide6 still validates the hub surface."""
    src = Path("nvra_unified/gui.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    required = {
        "client_setup_tab",
        "save_gemini",
        "test_gemini",
        "clear_gemini",
        "pick_google_client",
        "save_google_client",
        "test_exchange",
        "clear_exchange",
        "test_telegram",
        "clear_telegram",
        "detect_mt5",
        "refresh_setup_status",
        "test_all_safe",
        "save_exchange",
        "save_telegram",
        "setup_totp",
    }
    missing = required - methods
    assert not missing, f"Missing Client Setup methods: {sorted(missing)}"


def test_guard_blocks_when_not_logged_in(tmp_path, monkeypatch):
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from nvra_unified.runtime import UnifiedRuntime
    from nvra_unified.gui import NVRAUnifiedWindow

    app = QApplication.instance() or QApplication([])
    rt = UnifiedRuntime()
    win = NVRAUnifiedWindow(rt)
    assert win.logged_in is False
    assert win._guard() is False
