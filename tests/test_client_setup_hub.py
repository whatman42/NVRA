"""Client Setup Hub — presence of setup surfaces and login guard."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


def test_gui_source_has_client_setup_methods():
    """Static check so CI without display/Qt native libs still validates the hub surface."""
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
    """Runtime GUI guard check — requires a working Qt display stack.

    PySide6 wheels may install on Linux CI while system libs (e.g. libEGL.so.1)
    are absent; importorskip only covers the pure-Python package, so we must
    also catch native ImportError and skip rather than fail the whole matrix.
    """
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    pytest.importorskip("PySide6")
    try:
        from PySide6.QtWidgets import QApplication
        from nvra_unified.runtime import UnifiedRuntime
        from nvra_unified.gui import NVRAUnifiedWindow
    except ImportError as exc:
        # Missing libEGL / libGL / display on headless Linux runners
        msg = str(exc)
        if any(
            token in msg
            for token in (
                "libEGL",
                "libGL",
                "libOpenGL",
                "libxcb",
                "cannot open shared object",
            )
        ):
            pytest.skip(f"Qt native runtime unavailable on this host: {exc}")
        raise

    app = QApplication.instance() or QApplication([])
    rt = UnifiedRuntime()
    win = NVRAUnifiedWindow(rt)
    assert win.logged_in is False
    assert win._guard() is False
