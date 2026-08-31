"""MT5 Demo Adapter Gate — sequential E2E before any LIVE path.

Sequence:
  MT5 Adapter → Demo Connection → Market Data → Account State →
  Position Sync → Order Test (optional) → Fill Verification →
  Reconciliation → Recovery check → (only then) Live Gate eligibility note
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from god.broker.models import ProviderHealth
from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
from god.broker.mt5.models import MT5AccountMode, MT5OrderRequest


@dataclass
class DemoGateReport:
    overall: str  # PASS | FAIL | SKIPPED
    steps: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    account_mode: str = "UNKNOWN"
    live_eligible: bool = False  # always False here — DEMO gate never grants LIVE
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "steps": dict(self.steps),
            "reasons": list(self.reasons),
            "account_mode": self.account_mode,
            "live_eligible": False,
            "details": dict(self.details),
        }


class MT5DemoGate:
    """Run demo verification. Never enables LIVE."""

    def __init__(self, adapter: Optional[MT5ExecutionAdapter] = None) -> None:
        self.adapter = adapter or MT5ExecutionAdapter(
            MT5ConnectionConfig(allow_live_account=False)
        )

    def run(
        self,
        *,
        symbol: str = "EURUSD",
        submit_test_order: bool = False,
        test_volume: float = 0.01,
    ) -> DemoGateReport:
        steps: dict[str, str] = {}
        reasons: list[str] = []
        details: dict[str, Any] = {}

        # 1. Connect
        ok = self.adapter.connect()
        steps["demo_connection"] = "PASS" if ok else "FAIL"
        if not ok:
            reasons.append(self.adapter.last_error or "connect_failed")
            return DemoGateReport(
                overall="FAIL",
                steps=steps,
                reasons=reasons,
                account_mode=self.adapter.account_mode().value,
                live_eligible=False,
            )

        mode = self.adapter.account_mode()
        steps["account_mode"] = "PASS" if mode == MT5AccountMode.DEMO else "FAIL"
        if mode != MT5AccountMode.DEMO:
            reasons.append(f"expected_DEMO_got_{mode.value}")
            self.adapter.disconnect()
            return DemoGateReport(
                overall="FAIL",
                steps=steps,
                reasons=reasons,
                account_mode=mode.value,
                live_eligible=False,
            )

        # 2. Health
        h = self.adapter.health()
        steps["health"] = "PASS" if h == ProviderHealth.HEALTHY else "FAIL"
        if h != ProviderHealth.HEALTHY:
            reasons.append(f"health={h.value}")

        # 3. Account state
        acct = self.adapter.account_state()
        steps["account_state"] = "PASS" if acct.account_id else "FAIL"
        details["account_id_masked"] = (acct.account_id[:2] + "***") if acct.account_id else ""
        details["equity"] = acct.equity

        # 4. Market data
        tick = self.adapter.symbol_tick(symbol)
        steps["market_data"] = "PASS" if tick and tick.bid > 0 else "FAIL"
        if tick:
            details["tick"] = {"bid": tick.bid, "ask": tick.ask, "spread": tick.spread}
        else:
            reasons.append("no_tick")

        # 5. Position / order sync
        positions = self.adapter.open_positions()
        orders = self.adapter.orders()
        steps["position_sync"] = "PASS"
        steps["order_sync"] = "PASS"
        details["position_count"] = len(positions)
        details["order_count"] = len(orders)

        # 6. Optional minimal order test
        if submit_test_order:
            req = MT5OrderRequest(
                client_order_id="demo-gate-test-001",
                symbol=symbol,
                side="BUY",
                volume=test_volume,
                comment="NVRA_DEMO_GATE",
            )
            result = self.adapter.submit(req)
            steps["order_test"] = "PASS" if result.ok else "FAIL"
            details["order_result"] = result.to_dict()
            if not result.ok:
                reasons.append(result.message or "order_failed")
            # 7. Fill verification (best-effort)
            steps["fill_verification"] = (
                "PASS" if result.status in ("FILLED", "PARTIAL", "ACCEPTED") else "FAIL"
            )
        else:
            steps["order_test"] = "SKIPPED"
            steps["fill_verification"] = "SKIPPED"

        # 8. Reconciliation
        rec = self.adapter.reconcile()
        steps["reconciliation"] = "PASS" if rec.get("ok") else "FAIL"
        details["reconcile"] = {
            "mode": rec.get("mode"),
            "positions": len(rec.get("positions") or []),
        }

        # 9. Recovery marker (state is readable after ops)
        steps["recovery_check"] = "PASS" if self.adapter.health() != ProviderHealth.UNAVAILABLE else "FAIL"

        failed = [k for k, v in steps.items() if v == "FAIL"]
        overall = "FAIL" if failed else "PASS"
        if failed:
            reasons.append("failed_steps:" + ",".join(failed))

        # DEMO gate never sets live_eligible True
        return DemoGateReport(
            overall=overall,
            steps=steps,
            reasons=reasons,
            account_mode=mode.value,
            live_eligible=False,
            details=details,
        )
