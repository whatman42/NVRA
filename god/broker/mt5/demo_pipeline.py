"""DEMO-only execution pipeline: ML → signal → risk → adaptive sizing → MT5 DEMO order_send.

CapitalAdaptiveRiskEngine is the SOLE volume authority on this path.
Legacy compute_position_size is never called here.
LIVE is always rejected. No auto-trading on startup.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
from god.broker.mt5.models import MT5AccountMode, MT5OrderRequest, MT5OrderResult
from god.market_decision.engine import MarketDecisionEngine, MarketDecisionResult
from god.market_decision.quotes import Quote
from god.ml.evidence import MLEvidence
from god.ml.pipeline import MLPipeline, PipelineResult
from god.risk.account_snapshot import AccountSnapshot, AccountStateEngine
from god.risk.adaptive import AdaptiveRiskRequest, AdaptiveRiskResult, CapitalAdaptiveRiskEngine
from god.risk.broker_constraints import SymbolConstraints


@dataclass
class DemoPipelineResult:
    ok: bool
    stage: str
    reasons: list[str] = field(default_factory=list)
    account_mode: str = "UNKNOWN"
    ml: Optional[dict[str, Any]] = None
    decision: Optional[dict[str, Any]] = None
    sizing: Optional[dict[str, Any]] = None
    order: Optional[dict[str, Any]] = None
    positions: list[dict[str, Any]] = field(default_factory=list)
    live_blocked: bool = True
    exchange_submissions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "stage": self.stage,
            "reasons": list(self.reasons),
            "account_mode": self.account_mode,
            "ml": self.ml,
            "decision": self.decision,
            "sizing": self.sizing,
            "order": self.order,
            "positions": list(self.positions),
            "live_blocked": True,
            "exchange_submissions": self.exchange_submissions,
        }


class DemoOnlyExecutionPipeline:
    """
    Explicit DEMO path only.

    Volume authority: CapitalAdaptiveRiskEngine only.
    Guards:
    - account mode must be DEMO or CONTEST
    - LIVE always reject (even if config mis-set)
    - submit_order defaults False (opt-in)
    - adaptive NO TRADE ⇒ no order
    """

    def __init__(
        self,
        adapter: MT5ExecutionAdapter,
        *,
        ml_pipeline: Optional[MLPipeline] = None,
        decision_engine: Optional[MarketDecisionEngine] = None,
        risk_engine: Optional[CapitalAdaptiveRiskEngine] = None,
        account_engine: Optional[AccountStateEngine] = None,
        risk_pct: float = 0.01,
        stop_pips: float = 20.0,
        pip_size: float = 0.0001,
    ) -> None:
        self.adapter = adapter
        self.ml = ml_pipeline
        self.decision = decision_engine or MarketDecisionEngine()
        self.risk_engine = risk_engine or CapitalAdaptiveRiskEngine()
        self.account_engine = account_engine or AccountStateEngine()
        self.risk_pct = risk_pct
        self.stop_pips = stop_pips
        self.pip_size = pip_size

    def run(
        self,
        *,
        symbol: str = "EURUSD",
        closes: Optional[Sequence[float]] = None,
        regime: str = "TRENDING",
        submit_order: bool = False,
        ml_evidence: Optional[MLEvidence] = None,
    ) -> DemoPipelineResult:
        reasons: list[str] = []

        # 1. Connect + account mode guard
        if not self.adapter.connect():
            return DemoPipelineResult(
                ok=False,
                stage="connect",
                reasons=[self.adapter.last_error or "connect_failed"],
                live_blocked=True,
            )

        mode = self.adapter.account_mode()
        if mode == MT5AccountMode.LIVE:
            self.adapter.disconnect()
            return DemoPipelineResult(
                ok=False,
                stage="account_guard",
                reasons=["LIVE_account_rejected"],
                account_mode=mode.value,
                live_blocked=True,
            )
        if mode not in (MT5AccountMode.DEMO, MT5AccountMode.CONTEST):
            self.adapter.disconnect()
            return DemoPipelineResult(
                ok=False,
                stage="account_guard",
                reasons=[f"account_mode_not_demo:{mode.value}"],
                account_mode=mode.value,
                live_blocked=True,
            )

        # 2. Market data
        tick = self.adapter.symbol_tick(symbol)
        if tick is None or tick.bid <= 0:
            return DemoPipelineResult(
                ok=False,
                stage="market_data",
                reasons=["no_tick"],
                account_mode=mode.value,
            )

        quote = Quote(symbol, time.time(), bid=tick.bid, ask=tick.ask)
        closes_list = list(closes) if closes is not None else []

        # 3. ML (optional)
        ml_dict = None
        evidence = ml_evidence
        if evidence is None and self.ml is not None and len(closes_list) >= 50:
            pr: PipelineResult = self.ml.run(
                closes_list, symbol=symbol, regime=regime, promote_champion=False
            )
            evidence = pr.evidence
            ml_dict = pr.to_dict()

        # 4. Decision (ML-driven when gate open)
        self.decision.stream.on_message(sequence=1)
        decision: MarketDecisionResult = self.decision.run(
            quote=quote,
            closes=closes_list if closes_list else None,
            ml_evidence=evidence,
            reconciliation_healthy=True,
            now=time.time(),
        )

        # 5. Account state → snapshot (fail-closed)
        acct = self.adapter.account_state()
        validation = self.account_engine.from_provider_state(
            acct, now=time.time(), source="mt5_adapter"
        )
        snap = validation.snapshot
        if not validation.ok or snap is None:
            return DemoPipelineResult(
                ok=False,
                stage="account_state",
                reasons=list(validation.reasons),
                account_mode=mode.value,
                ml=ml_dict,
                decision=decision.to_dict() if hasattr(decision, "to_dict") else None,
                exchange_submissions=0,
            )

        # 6. Symbol constraints from broker (fail-closed)
        cons_val = self.adapter.symbol_constraints(symbol)
        if not cons_val.ok or cons_val.constraints is None:
            return DemoPipelineResult(
                ok=False,
                stage="constraints",
                reasons=list(cons_val.reasons) if cons_val.reasons else ["constraints_unavailable"],
                account_mode=mode.value,
                ml=ml_dict,
                decision=decision.to_dict() if hasattr(decision, "to_dict") else None,
                exchange_submissions=0,
            )
        constraints: SymbolConstraints = cons_val.constraints

        # 7. Adaptive sizing — SOLE volume authority
        stop_distance = self.stop_pips * self.pip_size
        spread_price = max(0.0, float(tick.ask) - float(tick.bid))
        req = AdaptiveRiskRequest(
            snapshot=snap,
            constraints=constraints,
            risk_pct=self.risk_pct,
            stop_loss_distance=stop_distance,
            spread_price=spread_price,
        )
        size: AdaptiveRiskResult = self.risk_engine.evaluate(req)

        if not size.ok or size.volume <= 0:
            return DemoPipelineResult(
                ok=False,
                stage="sizing",
                reasons=[size.reason or "no_trade"],
                account_mode=mode.value,
                ml=ml_dict,
                decision=decision.to_dict() if hasattr(decision, "to_dict") else None,
                sizing=size.to_dict(),
                exchange_submissions=0,
            )

        if not submit_order:
            return DemoPipelineResult(
                ok=True,
                stage="intent_only",
                reasons=["submit_order_false"],
                account_mode=mode.value,
                ml=ml_dict,
                decision=decision.to_dict() if hasattr(decision, "to_dict") else None,
                sizing=size.to_dict(),
                exchange_submissions=0,
            )

        # 8. Submit DEMO order only
        side = decision.intent.side if decision.intent else "BUY"
        mid = (tick.bid + tick.ask) / 2.0
        sl = mid - stop_distance if side == "BUY" else mid + stop_distance
        client_id = "demo-" + hashlib.sha256(
            f"{symbol}:{side}:{time.time()}".encode()
        ).hexdigest()[:16]
        req_order = MT5OrderRequest(
            client_order_id=client_id,
            symbol=symbol,
            side=side,
            volume=float(size.volume),
            sl=sl,
            comment="NVRA_DEMO_ADAPTIVE",
        )
        # Defense: re-check mode before order_send
        if self.adapter.account_mode() == MT5AccountMode.LIVE:
            return DemoPipelineResult(
                ok=False,
                stage="pre_submit_guard",
                reasons=["LIVE_rejected_before_send"],
                account_mode="LIVE",
                live_blocked=True,
            )

        result: MT5OrderResult = self.adapter.submit(req_order)
        positions = self.adapter.open_positions()
        submissions = 1 if result.ok else 0

        return DemoPipelineResult(
            ok=result.ok,
            stage="order_submitted" if result.ok else "order_rejected",
            reasons=[] if result.ok else [result.message or "order_failed"],
            account_mode=mode.value,
            ml=ml_dict,
            decision=decision.to_dict() if hasattr(decision, "to_dict") else None,
            sizing=size.to_dict(),
            order=result.to_dict(),
            positions=positions,
            exchange_submissions=submissions,
            live_blocked=True,
        )
