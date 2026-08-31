#!/usr/bin/env python3
"""Manual DEMO smoke test — opt-in via DEMO_SMOKE_TEST=true.

Default: does nothing (DEMO_SMOKE_TEST=false).
Never runs on application startup. Never touches LIVE.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    flag = os.environ.get("DEMO_SMOKE_TEST", "false").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        print("DEMO_SMOKE_TEST not enabled — exit 0 (no orders).")
        return 0

    # Prefer real MT5 if available; else refuse (smoke is for real DEMO terminal)
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError:
        print("MetaTrader5 not installed — cannot run real DEMO smoke.")
        print("Use unit tests with FakeMetaTrader5 for CI.")
        return 2

    from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
    from god.broker.mt5.demo_pipeline import DemoOnlyExecutionPipeline
    from god.broker.mt5.models import MT5AccountMode
    from god.ml.pipeline import MLPipeline

    submit = os.environ.get("DEMO_SMOKE_SUBMIT", "false").strip().lower() in ("1", "true", "yes")
    symbol = os.environ.get("DEMO_SMOKE_SYMBOL", "EURUSD")

    adapter = MT5ExecutionAdapter(MT5ConnectionConfig(allow_live_account=False))
    if not adapter.connect():
        print(f"connect failed: {adapter.last_error}")
        return 1
    mode = adapter.account_mode()
    if mode == MT5AccountMode.LIVE:
        print("LIVE account detected — abort (no orders).")
        adapter.disconnect()
        return 1
    if mode not in (MT5AccountMode.DEMO, MT5AccountMode.CONTEST):
        print(f"account mode {mode.value} not DEMO — abort.")
        adapter.disconnect()
        return 1

    rates = adapter.copy_rates(symbol, timeframe_minutes=60, count=200)
    closes = [float(r["close"]) for r in rates] if rates else []
    if len(closes) < 50:
        print("insufficient rates for ML")
        adapter.disconnect()
        return 1

    reg = Path(os.environ.get("DEMO_SMOKE_REGISTRY", ".ml_registry_smoke"))
    ml = MLPipeline(reg, load_champion=True)
    if ml._last_model is None:
        ml.run(closes, regime="TRENDING", promote_champion=True)

    pipe = DemoOnlyExecutionPipeline(adapter, ml_pipeline=ml)
    result = pipe.run(
        symbol=symbol,
        closes=closes,
        regime="TRENDING",
        submit_order=submit,
    )
    print(result.to_dict())

    # cleanup: close any position opened by this smoke if submit
    if submit and result.ok and result.positions:
        for p in result.positions:
            ticket = p.get("ticket")
            if ticket:
                adapter.close_position(int(ticket))
                print(f"closed ticket {ticket}")

    adapter.disconnect()
    return 0 if result.ok or result.stage in ("intent_only", "decision_no_entry") else 1


if __name__ == "__main__":
    sys.exit(main())
