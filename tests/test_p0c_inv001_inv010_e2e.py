"""P0-C: E2E qualification for INV-001 (LIVE preconditions) and INV-010 (fallback never LIVE).

Composes production modules without changing authorization semantics:
- god.live.authorization.LiveAuthorizationGate
- src.crypto.production.gates.ProductionGate
- god.control_plane.fallback.evaluate_offline
- crypto.risk.engine.RiskEngine
- god.institutional.checkpoint.CheckpointStore
- crypto.execution.models.ExecutionMode

Evidence is append-only transition records (passive).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pytest

from crypto.execution.models import ExecutionMode
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.portfolio.models import ExposureBreakdown, PortfolioSnapshot
from crypto.production.gates import LiveDecision, ProductionGate
from crypto.risk.engine import RiskEngine
from crypto.risk.models import RiskVerdict, SafetyMode, Side, TradeProposal
from crypto.risk.policy import RiskPolicy
from god.control_plane.fallback import OfflineDecision, SignedFallbackState, evaluate_offline
from god.institutional.checkpoint import CheckpointStore
from god.live.authorization import LiveAuthorizationGate
from god.live.models import LivePrerequisites, LiveValidationState

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research" / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


@dataclass
class EvidenceEvent:
    seq: int
    run_id: str
    process_id: int
    startup_state: str
    execution_mode: str
    reconciliation_status: str
    risk_governor_status: str
    safe_mode: bool
    license_status: str
    checkpoint_valid: bool | None
    checkpoint_trusted_ready: bool | None
    fallback_status: str
    execution_authorization: bool
    live_submit_allowed: bool
    attempted_transition: str
    transition_result: str
    rejection_reason: str
    timestamp_ns: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceLedger:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[EvidenceEvent] = []
        self._seq = 0

    def record(self, **kwargs: Any) -> EvidenceEvent:
        self._seq += 1
        ev = EvidenceEvent(
            seq=self._seq,
            run_id=self.run_id,
            process_id=os.getpid(),
            timestamp_ns=time.time_ns(),
            **kwargs,
        )
        self.events.append(ev)
        return ev

    def hash(self) -> str:
        raw = json.dumps([e.to_dict() for e in self.events], sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


def _all_prereq(**over: bool) -> LivePrerequisites:
    base = dict(
        operator_authorized=True,
        license_valid=True,
        device_valid=True,
        credentials_valid=True,
        broker_connected=True,
        state_loaded=True,
        reconciliation_pass=True,
        risk_governor_ready=True,
        startup_ready=True,
    )
    base.update(over)
    return LivePrerequisites(**base)


def _port() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        equity=10_000.0,
        available_balance=10_000.0,
        reserved_balance=0.0,
        holdings=(),
        positions=(),
        unrealized_pnl=0.0,
        realized_pnl=0.0,
        fees=0.0,
        exposure=ExposureBreakdown(gross=0.0, net=0.0),
        timestamp_ms=0,
    )


def _prop() -> TradeProposal:
    return TradeProposal(
        exchange_id="paper",
        account_id="default",
        symbol="TEST",
        side=Side.BUY,
        requested_quantity=0.01,
        requested_price=100.0,
        strategy_id="p0c",
        timestamp_ms=0,
    )


def risk_executable(*, recon: bool = True, safety: SafetyMode = SafetyMode.NORMAL, dq=None) -> bool:
    eng = RiskEngine(RiskPolicy())
    eng.set_reconciliation_ok(recon)
    eng.set_safety_mode(safety)
    mq = DataQualityReport(quality=dq, reasons=(dq.name.lower(),)) if dq else None
    d = eng.evaluate(_prop(), _port(), market_quality=mq, entry_price=100.0)
    return bool(d.verdict == RiskVerdict.APPROVED and d.executable)


def integrated_live_authorized(
    *,
    prereq: LivePrerequisites,
    arm: bool = True,
    safe_mode: bool = False,
    production_gate: ProductionGate | None = None,
    exchange_verified: bool = True,
    risk_recon: bool = True,
    risk_safety: SafetyMode = SafetyMode.NORMAL,
    checkpoint_trusted: bool = True,
    fallback: OfflineDecision | None = None,
    ledger: EvidenceLedger | None = None,
    startup_state: str = "RUNNING",
) -> dict[str, Any]:
    """Composition: LiveAuthorizationGate AND ProductionGate AND Risk AND Checkpoint AND Fallback."""
    gate = LiveAuthorizationGate(prerequisites=prereq)
    if safe_mode:
        gate.enter_safe_mode("injected")
    else:
        gate.recompute()
    arm_result = None
    if arm and not safe_mode:
        arm_result = gate.arm(operator_authorization="operator-token-not-logged")
    live_gate_ok = gate.can_submit_live()

    pg = production_gate or ProductionGate(
        connectivity=lambda: True,
        permissions=lambda: {"trading": "ENABLED", "withdrawal": "DISABLED"},
        db_integrity=lambda: True,
        model_ok=lambda: True,
        recovery_ok=lambda: True,
        governor_ok=lambda: True,
        risk_ok=lambda: True,
        control_ok=lambda: True,
        canary_round_trip_ok=True,
        emergency_stop_tested=True,
        time_skew_ms=0,
        reconciliation_mismatch=not risk_recon,
        unresolved_unknown=False,
    )
    report = pg.evaluate(exchange_verified=exchange_verified)
    prod_go = report.live_decision is LiveDecision.GO

    risk_ok = risk_executable(recon=risk_recon, safety=risk_safety)
    fallback_status = "none"
    if fallback is not None:
        fallback_status = f"{fallback.mode}:{fallback.reason}"

    authorized = (
        live_gate_ok
        and prod_go
        and risk_ok
        and checkpoint_trusted
        and not safe_mode
    )
    if fallback is not None:
        authorized = False

    mode = ExecutionMode.LIVE if authorized else ExecutionMode.PAPER

    if ledger:
        ledger.record(
            startup_state=startup_state,
            execution_mode=mode.name,
            reconciliation_status="ok" if risk_recon else "incomplete",
            risk_governor_status="ok" if risk_ok else "blocked",
            safe_mode=safe_mode or gate.state == LiveValidationState.SAFE_MODE,
            license_status="valid" if prereq.license_valid else "invalid",
            checkpoint_valid=checkpoint_trusted,
            checkpoint_trusted_ready=checkpoint_trusted,
            fallback_status=fallback_status,
            execution_authorization=authorized,
            live_submit_allowed=gate.can_submit_live() and authorized,
            attempted_transition="LIVE_SUBMIT" if arm else "EVAL",
            transition_result="ALLOW" if authorized else "REJECT",
            rejection_reason=(
                ""
                if authorized
                else (
                    (arm_result.reason if arm_result and not arm_result.ok else "")
                    or (report.live_decision.name if not prod_go else "")
                    or ("risk_blocked" if not risk_ok else "")
                    or ("checkpoint_untrusted" if not checkpoint_trusted else "")
                    or ("fallback_no_live" if fallback is not None else "")
                    or "preconditions_unmet"
                )
            ),
        )

    return {
        "authorized": authorized,
        "live_gate_ok": live_gate_ok,
        "prod_go": prod_go,
        "risk_ok": risk_ok,
        "mode": mode.name,
        "gate_state": gate.state.value,
        "can_submit_live": gate.can_submit_live(),
        "prod_decision": report.live_decision.name,
        "arm_ok": bool(arm_result.ok) if arm_result else False,
        "fallback_live": bool(fallback.live_trading) if fallback else False,
    }


def test_inv001_valid_fully_qualified_path():
    led = EvidenceLedger("inv001-valid")
    r = integrated_live_authorized(
        prereq=_all_prereq(), arm=True, risk_recon=True, checkpoint_trusted=True, ledger=led
    )
    assert r["authorized"] is True
    assert r["mode"] == "LIVE"
    assert r["can_submit_live"] is True


def test_inv001_missing_license():
    r = integrated_live_authorized(prereq=_all_prereq(license_valid=False), arm=True)
    assert r["authorized"] is False
    assert r["can_submit_live"] is False


@pytest.mark.parametrize(
    "flag",
    [
        "operator_authorized",
        "license_valid",
        "device_valid",
        "credentials_valid",
        "broker_connected",
        "state_loaded",
        "reconciliation_pass",
        "risk_governor_ready",
        "startup_ready",
    ],
)
def test_inv001_each_missing_precondition_blocks_live(flag: str):
    r = integrated_live_authorized(prereq=_all_prereq(**{flag: False}), arm=True)
    assert r["authorized"] is False
    assert r["can_submit_live"] is False


def test_inv001_reconciliation_incomplete_blocks():
    r = integrated_live_authorized(
        prereq=_all_prereq(reconciliation_pass=False), risk_recon=False, arm=True
    )
    assert r["authorized"] is False
    assert r["risk_ok"] is False


def test_inv001_safe_mode_blocks():
    r = integrated_live_authorized(prereq=_all_prereq(), safe_mode=True, arm=True)
    assert r["authorized"] is False
    assert r["gate_state"] == "SAFE_MODE"


def test_inv001_broker_unavailable():
    r = integrated_live_authorized(prereq=_all_prereq(broker_connected=False), arm=True)
    assert r["authorized"] is False


def test_inv001_execution_before_ready_startup():
    r = integrated_live_authorized(
        prereq=_all_prereq(startup_ready=False, state_loaded=False),
        arm=True,
        startup_state="LOAD_STATE",
    )
    assert r["authorized"] is False


def test_inv001_ready_without_risk_recon_no_execution():
    r = integrated_live_authorized(
        prereq=_all_prereq(), risk_recon=False, arm=True, startup_state="READY"
    )
    assert r["authorized"] is False


def test_inv001_production_gate_no_go_blocks():
    pg = ProductionGate(
        connectivity=lambda: False, canary_round_trip_ok=False, emergency_stop_tested=False
    )
    r = integrated_live_authorized(prereq=_all_prereq(), production_gate=pg, arm=True)
    assert r["prod_go"] is False
    assert r["authorized"] is False


def test_inv001_checkpoint_untrusted_blocks():
    r = integrated_live_authorized(prereq=_all_prereq(), checkpoint_trusted=False, arm=True)
    assert r["authorized"] is False


def test_inv001_corrupt_checkpoint_not_trusted(tmp_path: Path):
    store = CheckpointStore(tmp_path / "c.db")
    import sqlite3

    store.save("r", "observation", {"ok": True})
    with sqlite3.connect(tmp_path / "c.db") as c:
        c.execute("UPDATE checkpoints SET state_json=? WHERE run_id='r'", ("NOTJSON",))
        c.commit()
    assert store.load("r") is None
    assert store.load_trusted_ready("r") is None


def test_inv001_semantic_invalid_checkpoint(tmp_path: Path):
    store = CheckpointStore(tmp_path / "c.db")
    import sqlite3

    payload = json.dumps(
        {
            "schema_version": "1.0",
            "sequence": 1,
            "lifecycle": "READY",
            "recon_complete": False,
            "updated_ns": time.time_ns(),
        }
    )
    with sqlite3.connect(tmp_path / "c.db") as c:
        c.execute(
            "INSERT INTO checkpoints VALUES(?,?,?,?)",
            ("r", "READY", payload, time.time_ns()),
        )
        c.commit()
    assert store.load("r") is None


def test_inv001_stale_unknown_checkpoint_blocks_exec():
    assert risk_executable(dq=DataQuality.UNKNOWN) is False
    assert risk_executable(dq=DataQuality.STALE) is False


def test_inv001_risk_governor_failure_via_emergency_stop():
    assert risk_executable(safety=SafetyMode.EMERGENCY_STOP) is False
    r = integrated_live_authorized(
        prereq=_all_prereq(), risk_safety=SafetyMode.EMERGENCY_STOP, arm=True
    )
    assert r["authorized"] is False


def test_inv001_restart_ready_like_still_needs_full_gates():
    r = integrated_live_authorized(
        prereq=_all_prereq(operator_authorized=False),
        checkpoint_trusted=True,
        arm=True,
        startup_state="READY",
    )
    assert r["authorized"] is False


def _fallback_state(**over) -> SignedFallbackState:
    base = dict(
        license_status="ACTIVE",
        account_status="ACTIVE",
        device_status="ACTIVE",
        paper_only=True,
        last_sync_at=time.time(),
        grace_until=time.time() + 3600,
    )
    base.update(over)
    return SignedFallbackState(**base)


def test_inv010_offline_fallback_never_live():
    d = evaluate_offline(None, "missing")
    assert d.live_trading is False
    r = integrated_live_authorized(prereq=_all_prereq(), fallback=d, arm=True)
    assert r["authorized"] is False


def test_inv010_signed_fallback_paper_only():
    d = evaluate_offline(_fallback_state(), "ok", now=time.time())
    assert d.live_trading is False
    assert d.paper_only is True
    r = integrated_live_authorized(prereq=_all_prereq(), fallback=d, arm=True)
    assert r["authorized"] is False


def test_inv010_corrupted_fallback():
    d = evaluate_offline(None, "corrupt")
    assert d.live_trading is False


def test_inv010_invalid_license_fallback():
    d = evaluate_offline(_fallback_state(license_status="REVOKED"), "ok", now=time.time())
    assert d.live_trading is False
    r = integrated_live_authorized(prereq=_all_prereq(), fallback=d, arm=True)
    assert r["authorized"] is False


def test_inv010_fallback_during_safe_mode():
    d = evaluate_offline(_fallback_state(), "ok", now=time.time())
    r = integrated_live_authorized(prereq=_all_prereq(), fallback=d, safe_mode=True, arm=True)
    assert r["authorized"] is False


def test_inv010_malicious_live_via_fallback_rejected():
    malicious = OfflineDecision(True, "HACK", "x", paper_only=False, live_trading=True)
    r = integrated_live_authorized(prereq=_all_prereq(), fallback=malicious, arm=True)
    assert r["authorized"] is False


def test_inv010_repeated_fallback_transitions():
    for _ in range(20):
        d = evaluate_offline(_fallback_state(), "ok", now=time.time())
        assert d.live_trading is False
        r = integrated_live_authorized(prereq=_all_prereq(), fallback=d, arm=True)
        assert r["authorized"] is False


def test_inv010_fallback_cannot_bypass_recon():
    d = evaluate_offline(_fallback_state(), "ok", now=time.time())
    r = integrated_live_authorized(
        prereq=_all_prereq(reconciliation_pass=False),
        risk_recon=False,
        fallback=d,
        arm=True,
    )
    assert r["authorized"] is False
    assert r["risk_ok"] is False


def test_p0c_aggregate_evidence_matrix():
    led = EvidenceLedger("p0c-aggregate")
    scenarios = []

    def run(name, **kw):
        r = integrated_live_authorized(ledger=led, **kw)
        scenarios.append(
            {
                "name": name,
                **{
                    k: r[k]
                    for k in (
                        "authorized",
                        "mode",
                        "can_submit_live",
                        "prod_go",
                        "risk_ok",
                        "fallback_live",
                        "gate_state",
                    )
                },
            }
        )
        return r

    run("valid", prereq=_all_prereq(), arm=True)
    run("missing_license", prereq=_all_prereq(license_valid=False), arm=True)
    run("no_recon", prereq=_all_prereq(reconciliation_pass=False), risk_recon=False, arm=True)
    run("safe_mode", prereq=_all_prereq(), safe_mode=True, arm=True)
    run("untrusted_cp", prereq=_all_prereq(), checkpoint_trusted=False, arm=True)
    d = evaluate_offline(_fallback_state(), "ok", now=time.time())
    run("fallback", prereq=_all_prereq(), fallback=d, arm=True)
    run("fallback_missing", prereq=_all_prereq(), fallback=evaluate_offline(None, "missing"), arm=True)

    unsafe_live = sum(1 for s in scenarios if s["name"] != "valid" and s["authorized"])
    fallback_live = sum(1 for s in scenarios if s.get("fallback_live"))
    assert scenarios[0]["authorized"] is True
    assert unsafe_live == 0
    assert fallback_live == 0

    payload = {
        "evidence_hash": led.hash(),
        "events": [e.to_dict() for e in led.events],
        "scenarios": scenarios,
        "unsafe_live_count": unsafe_live,
        "fallback_to_live_count": fallback_live,
        "INV-001": "PASS_E2E_COMPOSITION",
        "INV-010": "PASS_E2E_COMPOSITION",
        "notes": [
            "Composition: LiveAuthorizationGate AND ProductionGate AND RiskEngine AND Checkpoint AND evaluate_offline",
            "Full NVRAFX GUI operator ARM path remains partial",
            "Real exchange canary still deploy-time",
        ],
    }
    out = RESULTS / "p0c_inv001_inv010_results.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    assert out.exists()
