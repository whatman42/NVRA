#!/usr/bin/env python3
"""OS-level recovery worker for P0-B process-kill qualification.

Runs as a real child process. Progresses through lifecycle stages, persists
institutional checkpoints, then sleeps so the parent can SIGKILL it.

Recover mode loads checkpoint and writes a recovery verdict JSON.
Does NOT grant execution authority from checkpoint alone.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from god.institutional.checkpoint import CheckpointStore  # noqa: E402
from god.institutional.checkpoint_schema import validate_lifecycle_state  # noqa: E402
from crypto.risk.engine import RiskEngine  # noqa: E402
from crypto.risk.policy import RiskPolicy  # noqa: E402
from crypto.risk.models import SafetyMode, Side, TradeProposal, RiskVerdict  # noqa: E402
from crypto.portfolio.models import PortfolioSnapshot, ExposureBreakdown  # noqa: E402
from crypto.market.quality import DataQuality, DataQualityReport  # noqa: E402

STAGES = [
    "INIT",
    "LOAD_STATE",
    "BROKER_CONNECT",
    "RECONCILIATION",
    "RISK_GOVERNOR",
    "READY",
    "RUNNING",
]


def _port():
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


def _prop():
    return TradeProposal(
        exchange_id="paper",
        account_id="default",
        symbol="TEST",
        side=Side.BUY,
        requested_quantity=0.01,
        requested_price=100.0,
        strategy_id="p0b",
        timestamp_ms=0,
    )


def risk_allows(*, recon: bool, safety: SafetyMode = SafetyMode.NORMAL, dq=None) -> bool:
    eng = RiskEngine(RiskPolicy())
    eng.set_reconciliation_ok(recon)
    eng.set_safety_mode(safety)
    mq = DataQualityReport(quality=dq, reasons=(dq.name.lower(),)) if dq else None
    d = eng.evaluate(_prop(), _port(), market_quality=mq, entry_price=100.0)
    return bool(d.verdict == RiskVerdict.APPROVED and d.executable)


def write_status(workdir: Path, **fields) -> None:
    path = workdir / "status.json"
    payload = {"pid": os.getpid(), "ts_ns": time.time_ns(), **fields}
    path.write_text(json.dumps(payload, sort_keys=True))


def run_progress(workdir: Path, stop_after: str, corrupt: str | None) -> None:
    db = workdir / "checkpoints.db"
    store = CheckpointStore(db)
    run_id = "p0b-run"
    recon_complete = False
    seq = 0

    for stage in STAGES:
        seq += 1
        if stage == "RECONCILIATION":
            recon_complete = True
        if stage in ("READY", "RUNNING") and not recon_complete:
            write_status(workdir, stage=stage, error="blocked_ready_without_recon")
            time.sleep(3600)
            return

        state = {
            "schema_version": "1.0",
            "sequence": seq,
            "lifecycle": stage,
            "recon_complete": recon_complete,
            "updated_ns": time.time_ns(),
        }
        if corrupt == "before_save" and stage == stop_after:
            write_status(workdir, stage=stage, phase="before_save")
            time.sleep(3600)
            return

        if corrupt == "semantic_invalid" and stage == stop_after:
            bad = {
                "schema_version": "1.0",
                "sequence": seq,
                "lifecycle": "READY",
                "recon_complete": False,
                "updated_ns": time.time_ns(),
            }
            try:
                store.save(run_id, "READY", bad)
                write_status(workdir, stage=stage, phase="semantic_invalid_saved", ok=False)
            except Exception as e:
                write_status(
                    workdir,
                    stage=stage,
                    phase="semantic_invalid_rejected",
                    ok=True,
                    error=type(e).__name__,
                )
            time.sleep(3600)
            return

        store.save(run_id, stage, state)
        write_status(workdir, stage=stage, phase="after_save", seq=seq, recon=recon_complete)

        if stage == stop_after:
            if corrupt == "partial_write":
                import sqlite3

                with sqlite3.connect(db) as c:
                    c.execute(
                        "UPDATE checkpoints SET state_json=? WHERE run_id=?",
                        ('{"lifecycle":"RUNNING"', run_id),
                    )
                    c.commit()
                write_status(workdir, stage=stage, phase="partial_write_injected")
            time.sleep(3600)
            return

    write_status(workdir, stage="DONE", phase="complete")
    time.sleep(3600)


def recover(workdir: Path) -> dict:
    db = workdir / "checkpoints.db"
    store = CheckpointStore(db)
    run_id = "p0b-run"
    t0 = time.time_ns()
    loaded = store.load(run_id)
    t_load = time.time_ns()
    trusted = store.load_trusted_ready(run_id)
    t_trust = time.time_ns()

    validation = (loaded or {}).get("validation") or {}
    state = (loaded or {}).get("state") or {}
    node = (loaded or {}).get("node")

    recon = bool(state.get("recon_complete"))
    lifecycle = state.get("lifecycle") or node

    safety = SafetyMode.NORMAL
    if lifecycle == "SAFE_MODE" or validation.get("classification") == "SAFE_MODE":
        safety = SafetyMode.EMERGENCY_STOP

    exec_allowed = False
    if trusted is not None and recon and safety == SafetyMode.NORMAL:
        exec_allowed = risk_allows(recon=True, safety=safety)
    if trusted is None:
        exec_allowed = False
    if validation.get("classification") in ("UNKNOWN", "SAFE_MODE"):
        exec_allowed = False
    if not recon:
        exec_allowed = False

    unknown_exec = risk_allows(recon=True, dq=DataQuality.UNKNOWN)

    result = {
        "loaded": loaded is not None,
        "trusted_ready": trusted is not None,
        "trusted_execution_from_checkpoint": False,
        "execution_allowed": exec_allowed,
        "unsafe_ready": bool(trusted is not None and not recon),
        "unsafe_execution": bool(exec_allowed and (not recon or trusted is None)),
        "lifecycle": lifecycle,
        "recon_complete": recon,
        "validation_classification": validation.get("classification"),
        "unknown_dq_exec": unknown_exec,
        "timings_ns": {
            "recover_start": t0,
            "after_load": t_load,
            "after_trust_check": t_trust,
            "load_ms": (t_load - t0) / 1e6,
            "trust_ms": (t_trust - t0) / 1e6,
        },
        "pid": os.getpid(),
    }
    (workdir / "recovery_result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--mode", choices=("run", "recover"), required=True)
    ap.add_argument("--stop-after", default="RUNNING")
    ap.add_argument("--corrupt", default=None)
    args = ap.parse_args()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if args.mode == "run":
        write_status(workdir, stage="STARTING", phase="boot")
        run_progress(workdir, args.stop_after, args.corrupt)
        return 0
    recover(workdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
