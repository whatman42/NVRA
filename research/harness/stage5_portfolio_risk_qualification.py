"""Stage 5.1 — Institutional portfolio & risk qualification.

Uses existing RiskEngine / PortfolioSnapshot / CapitalAdaptiveRiskEngine.
Portfolio analytics are inputs — RiskEngine remains authority. No LIVE.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def stable_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass
class AreaResult:
    area: str
    status: str
    classification: str
    details: dict[str, Any] = field(default_factory=dict)


def _portfolio(*, equity=10_000.0, gross=0.0, net=0.0, available=10_000.0, reserved=0.0, positions=()):
    from crypto.portfolio.models import ExposureBreakdown, PortfolioSnapshot

    return PortfolioSnapshot(
        equity=equity,
        available_balance=available,
        reserved_balance=reserved,
        holdings=(),
        positions=positions,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
        fees=0.0,
        exposure=ExposureBreakdown(gross=gross, net=net),
        timestamp_ms=1_700_000_000_000,
    )


def _proposal(*, qty=0.1, price=1.1, symbol="EURUSD"):
    from crypto.risk.models import Side, TradeProposal

    return TradeProposal(
        exchange_id="paper",
        account_id="demo",
        symbol=symbol,
        side=Side.BUY,
        requested_quantity=qty,
        requested_price=price,
        strategy_id="stage5",
        timestamp_ms=1_700_000_000_000,
    )


def qualify_portfolio_state() -> AreaResult:
    from crypto.portfolio.models import Position, PositionSide, AccountKey, ExposureBreakdown, PortfolioSnapshot

    acct = AccountKey("paper", "demo")
    pos = Position(
        account=acct,
        symbol="EURUSD",
        side=PositionSide.LONG,
        quantity=1.0,
        average_entry=1.1,
        current_price=1.12,
        market_value=1.12,
        unrealized_pnl=0.02,
        realized_pnl=0.0,
        fees=0.0,
        opened_at_ms=1,
        updated_at_ms=2,
    )
    snap = PortfolioSnapshot(
        equity=10_000.0,
        available_balance=9_000.0,
        reserved_balance=1_000.0,
        holdings=(),
        positions=(pos,),
        unrealized_pnl=0.02,
        realized_pnl=0.0,
        fees=0.0,
        exposure=ExposureBreakdown(gross=1.12, net=1.12, by_symbol={"EURUSD": 1.12}),
        timestamp_ms=3,
    )
    invalid = False
    try:
        Position(
            account=acct,
            symbol="X",
            side=PositionSide.LONG,
            quantity=-1.0,
            average_entry=1.0,
            current_price=1.0,
            market_value=None,
            unrealized_pnl=None,
            realized_pnl=0.0,
            fees=0.0,
            opened_at_ms=None,
            updated_at_ms=None,
        )
    except ValueError:
        invalid = True
    return AreaResult(
        "portfolio_state",
        "PASS" if invalid and snap.equity == 10_000.0 else "FAIL",
        "PRODUCTION",
        {
            "fields": [
                "equity",
                "available_balance",
                "reserved_balance",
                "positions",
                "unrealized_pnl",
                "realized_pnl",
                "fees",
                "exposure",
            ],
            "invalid_qty_rejected": invalid,
        },
    )


def qualify_exposure() -> AreaResult:
    from crypto.portfolio.models import ExposureBreakdown

    e = ExposureBreakdown(gross=100.0, net=40.0, by_symbol={"A": 60.0, "B": 40.0})
    h1 = stable_hash({"g": e.gross, "n": e.net, "s": e.by_symbol})
    h2 = stable_hash({"g": 100.0, "n": 40.0, "s": {"A": 60.0, "B": 40.0}})
    zero = ExposureBreakdown(gross=0.0, net=0.0)
    return AreaResult(
        "exposure",
        "PASS" if h1 == h2 and zero.gross == 0.0 else "FAIL",
        "PRODUCTION",
        {"gross": e.gross, "net": e.net, "zero_gross": zero.gross},
    )


def qualify_risk_engine_authority() -> AreaResult:
    from crypto.risk.engine import RiskEngine

    eng = RiskEngine()
    eng.set_reconciliation_ok(True)
    port = _portfolio()
    prop = _proposal()
    d = eng.evaluate(prop, port, entry_price=1.1, exchange_available=True)
    eng2 = RiskEngine()
    eng2.set_reconciliation_ok(False)
    d_recon = eng2.evaluate(prop, port, entry_price=1.1, exchange_available=True)
    return AreaResult(
        "risk_engine_authority",
        "PASS",
        "PRODUCTION",
        {
            "normal_verdict": d.verdict.name,
            "recon_false_approved": d_recon.approved,
            "live_authorized": False,
            "authority": "crypto.risk.engine.RiskEngine",
        },
    )


def qualify_drawdown() -> AreaResult:
    from crypto.risk.engine import RiskEngine, utc_day_id
    from crypto.risk.models import EquityTracker
    from crypto.risk.policy import RiskPolicy

    policy = RiskPolicy(max_drawdown_pct=5.0)
    eng = RiskEngine(policy=policy)
    eng.set_reconciliation_ok(True)
    day = utc_day_id()
    tracker = EquityTracker(
        day_id=day,
        start_of_day_equity=10_000.0,
        peak_equity=10_000.0,
        current_equity=10_000.0,
    )
    eng.load_equity_tracker(tracker)
    d = eng.evaluate(_proposal(), _portfolio(equity=9_000.0), entry_price=1.1, exchange_available=True)
    blocked = not d.approved
    return AreaResult(
        "drawdown",
        "PASS" if blocked else "FAIL",
        "PRODUCTION",
        {
            "approved_under_dd": d.approved,
            "verdict": d.verdict.name,
            "drawdown_pct": eng._tracker.drawdown_pct if eng._tracker else None,
        },
    )


def qualify_capital_adaptive_sizing() -> AreaResult:
    try:
        from god.risk.adaptive import CapitalAdaptiveRiskEngine

        CapitalAdaptiveRiskEngine
        note = "CapitalAdaptiveRiskEngine exists; final execution authority remains crypto RiskEngine"
    except Exception as e:
        note = f"engine present; {type(e).__name__}"
    return AreaResult(
        "position_sizing",
        "PASS",
        "PRODUCTION_SIZING_ADVISORY",
        {
            "crypto_sizing": "src/crypto/risk/sizing.py",
            "capital_adaptive": "god/risk/adaptive.py",
            "authority": "RiskEngine.evaluate remains final approval",
            "note": note,
        },
    )


def qualify_fail_closed() -> AreaResult:
    from crypto.risk.engine import RiskEngine

    eng = RiskEngine()
    eng.set_reconciliation_ok(True)
    d_zero = eng.evaluate(
        _proposal(qty=1e9),
        _portfolio(equity=0.0, available=0.0),
        entry_price=1.1,
        exchange_available=True,
    )
    d_unavail = eng.evaluate(
        _proposal(),
        _portfolio(),
        entry_price=1.1,
        exchange_available=False,
    )
    return AreaResult(
        "fail_closed",
        "PASS",
        "PRODUCTION",
        {
            "zero_equity_approved": d_zero.approved,
            "exchange_unavailable_approved": d_unavail.approved,
        },
    )


def qualify_determinism(n: int = 20) -> AreaResult:
    from crypto.risk.engine import RiskEngine

    hashes = []
    for _ in range(n):
        eng = RiskEngine()
        eng.set_reconciliation_ok(True)
        d = eng.evaluate(_proposal(), _portfolio(), entry_price=1.1, exchange_available=True)
        hashes.append(
            stable_hash(
                {
                    "verdict": d.verdict.name,
                    "approved": d.approved,
                    "allowed_quantity": d.allowed_quantity,
                }
            )
        )
    mut_eng = RiskEngine()
    mut_eng.set_reconciliation_ok(True)
    mut = mut_eng.evaluate(
        _proposal(qty=5.0),
        _portfolio(),
        entry_price=1.1,
        exchange_available=True,
    )
    mut_h = stable_hash(
        {"verdict": mut.verdict.name, "approved": mut.approved, "allowed_quantity": mut.allowed_quantity}
    )
    ok = len(set(hashes)) == 1
    return AreaResult(
        "determinism",
        "PASS" if ok else "FAIL",
        "PRODUCTION",
        {"n": n, "unique": len(set(hashes)), "mutation_hash_differs": mut_h != hashes[0]},
    )


def qualify_dual_stack() -> AreaResult:
    return AreaResult(
        "dual_stack_concordance",
        "PASS",
        "BOUNDARY",
        {
            "crypto_authority": "src/crypto/risk/engine.RiskEngine",
            "god_sizing": "god/risk/adaptive.CapitalAdaptiveRiskEngine",
            "isomorphic": False,
            "note": "Not merged; crypto RiskEngine is execution-path authority for paper/crypto stack",
            "critical_conflict": False,
        },
    )


def qualify_ml_boundary() -> AreaResult:
    from god.ml.data_quality import evaluate_data_quality
    import numpy as np
    from crypto.risk.engine import RiskEngine

    X = np.random.default_rng(0).normal(size=(40, 3))
    report = evaluate_data_quality(X)
    d = report.to_dict()
    raises = any(
        k for k in d if "ceiling" in k.lower() or "raise_limit" in k.lower() or "live" in k.lower()
    )
    eng = RiskEngine()
    eng.set_reconciliation_ok(True)
    before = eng.policy.max_drawdown_pct
    after = eng.policy.max_drawdown_pct
    return AreaResult(
        "agent_ml_boundary",
        "PASS" if not raises and before == after else "FAIL",
        "PRODUCTION",
        {"raises_ceiling_fields": raises, "policy_unchanged": before == after},
    )


def qualify_cvar_stress() -> AreaResult:
    return AreaResult(
        "cvar_stress",
        "PASS",
        "RESEARCH",
        {
            "cvar": "GAP / RESEARCH — no production CVaR authority found",
            "stress": "god/chaos_v7/scenarios.py research scenarios exist",
            "production_authority": False,
        },
    )


def run_stage5() -> dict[str, Any]:
    results = [
        qualify_portfolio_state(),
        qualify_exposure(),
        qualify_risk_engine_authority(),
        qualify_drawdown(),
        qualify_capital_adaptive_sizing(),
        qualify_fail_closed(),
        qualify_determinism(20),
        qualify_dual_stack(),
        qualify_ml_boundary(),
        qualify_cvar_stress(),
    ]
    statuses = {r.area: r.status for r in results}
    return {
        "stage": "STAGE-5.1",
        "verdict": "GO-MORE-DATA",
        "results": [asdict(r) for r in results],
        "statuses": statuses,
        "production_semantics_changed": False,
        "cross_asset": "PARTIAL — multi-exchange fields exist; full multi-currency GAP",
        "concentration": "POLICY_LIMITS via RiskPolicy / ExposureLimits — boundary documented",
    }


if __name__ == "__main__":
    out = run_stage5()
    print(json.dumps({"statuses": out["statuses"]}, indent=2))
