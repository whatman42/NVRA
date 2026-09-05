"""Public MT5 diagnostic helper — module vs terminal vs initialize."""
from __future__ import annotations

from typing import Any

from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter


def diagnose_mt5(config: MT5ConnectionConfig | None = None) -> dict[str, Any]:
    adapter = MT5ExecutionAdapter(config or MT5ConnectionConfig(), mt5_module=None)
    if hasattr(adapter, "diagnose"):
        return adapter.diagnose()
    try:
        adapter._load_module()
        return {"python_module": "available", "live_authorized": False, "error": ""}
    except Exception as exc:
        return {
            "python_module": "missing",
            "live_authorized": False,
            "error": str(exc),
        }
