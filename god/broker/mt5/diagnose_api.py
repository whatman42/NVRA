"""Public MT5 diagnostic helper — module vs terminal vs initialize. Never enables LIVE."""
from __future__ import annotations

import importlib
from typing import Any

from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
from god.broker.mt5.errors import MT5NotAvailableError


def diagnose_mt5(config: MT5ConnectionConfig | None = None) -> dict[str, Any]:
    cfg = config or MT5ConnectionConfig()
    out: dict[str, Any] = {
        "python_module": "missing",
        "terminal_path": cfg.path or "",
        "initialize": "not_attempted",
        "account_info": "not_attempted",
        "connected": False,
        "live_authorized": False,
        "error": "",
    }
    adapter = MT5ExecutionAdapter(cfg, mt5_module=None)
    adapter._mt5 = None
    if hasattr(adapter, "diagnose"):
        d = adapter.diagnose()
        d["live_authorized"] = False
        return d
    try:
        mt5 = importlib.import_module("MetaTrader5")
        out["python_module"] = "available"
    except ModuleNotFoundError as exc:
        out["error"] = (
            "python_module_missing: MetaTrader5 package not in this runtime "
            f"(NVRA.exe must embed MetaTrader5; terminal install alone is not enough): {exc}"
        )
        return out
    except Exception as exc:
        out["error"] = f"MetaTrader5 unavailable: {exc}"
        return out
    try:
        kwargs: dict[str, Any] = {}
        if cfg.path:
            kwargs["path"] = cfg.path
        if cfg.timeout_ms:
            kwargs["timeout"] = cfg.timeout_ms
        if cfg.portable:
            kwargs["portable"] = True
        ok = bool(mt5.initialize(**kwargs))
        if not ok:
            err = mt5.last_error() if hasattr(mt5, "last_error") else "initialize_failed"
            out["initialize"] = "failed"
            out["error"] = f"terminal_or_initialize_failed:{err}"
            return out
        out["initialize"] = "ok"
        info = mt5.account_info() if hasattr(mt5, "account_info") else None
        if info is None:
            out["account_info"] = "failed"
            out["error"] = "account_info_failed"
        else:
            out["account_info"] = "ok"
            out["connected"] = True
        try:
            mt5.shutdown()
        except Exception:
            pass
    except Exception as exc:
        out["initialize"] = "exception"
        out["error"] = f"diagnose_exception:{type(exc).__name__}"
    out["live_authorized"] = False
    return out
