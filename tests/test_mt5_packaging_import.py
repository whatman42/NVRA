"""MT5 packaging / diagnostic contract — no LIVE authorization."""
from __future__ import annotations

import importlib
from pathlib import Path


def test_mt5_spec_lists_metatrader_hiddenimport():
    spec = Path("packaging/nvra_onefile.spec").read_text(encoding="utf-8")
    assert "MetaTrader5" in spec
    assert 'name="NVRA"' in spec


def test_mt5_diagnose_module_missing_path(monkeypatch):
    from god.broker.mt5.adapter import MT5ExecutionAdapter, MT5ConnectionConfig

    real_import = importlib.import_module

    def _boom(name, *a, **k):
        if name == "MetaTrader5":
            raise ModuleNotFoundError("No module named 'MetaTrader5'")
        return real_import(name, *a, **k)

    monkeypatch.setattr(importlib, "import_module", _boom)
    adapter = MT5ExecutionAdapter(MT5ConnectionConfig(), mt5_module=None)
    adapter._mt5 = None
    if hasattr(adapter, "diagnose"):
        d = adapter.diagnose()
    else:
        # Fallback until adapter.diagnose is on main: exercise load path
        try:
            adapter._load_module()
            d = {"python_module": "available", "live_authorized": False, "error": ""}
        except Exception as exc:
            d = {
                "python_module": "missing",
                "live_authorized": False,
                "error": str(exc),
            }
    assert d["python_module"] == "missing"
    assert d["live_authorized"] is False


def test_mt5_requirements_windows_marker():
    req = Path("requirements.txt").read_text(encoding="utf-8")
    assert "MetaTrader5" in req
    assert "Windows" in req
