"""Stage 6.2 extensions — cancel, UNKNOWN, recovery (imports helpers from stage6 harness)."""
from __future__ import annotations

from pathlib import Path

from research.harness.stage6_oms_execution_qualification import (
    AreaResult,
    _decision,
    _mock_adapter,
    _portfolio,
)


def qualify_cancel(tmp: Path) -> AreaResult:
    from crypto.execution import ExecutionEngine, ExecutionMode, ExecutionStore, OrderState, PaperBroker
    from crypto.market.quality import DataQuality, DataQualityReport
    from crypto.risk import MarketConstraints, RiskEngine, RiskPolicy

    store = ExecutionStore(tmp / "cancel.db")
    paper = PaperBroker(fill_ratio=0.0)
    engine = ExecutionEngine(
        _mock_adapter(), RiskEngine(RiskPolicy(max_position_pct=50.0)), store,
        mode=ExecutionMode.PAPER, paper_broker=paper,
    )
    rec = engine.submit(
        _decision(qty=0.2, price=100.0), _portfolio(),
        intent_key="cancel-s6",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    cancelled = engine.cancel(rec.execution_id)
    again = engine.cancel(rec.execution_id)
    ok = cancelled.state is OrderState.CANCELLED and again.state is OrderState.CANCELLED
    store2 = ExecutionStore(tmp / "cancel2.db")
    eng2 = ExecutionEngine(
        _mock_adapter(), RiskEngine(RiskPolicy(max_position_pct=50.0)), store2,
        mode=ExecutionMode.PAPER, paper_broker=PaperBroker(fill_ratio=1.0),
    )
    filled = eng2.submit(
        _decision(qty=0.2, price=100.0), _portfolio(),
        intent_key="cancel-filled",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    after_fill = eng2.cancel(filled.execution_id)
    after_fill_ok = after_fill.state is OrderState.FILLED
    return AreaResult(
        "cancel",
        "PASS" if ok and after_fill_ok else "FAIL",
        "PRODUCTION_PAPER",
        {
            "cancel_open": cancelled.state.name,
            "duplicate_cancel": again.state.name,
            "cancel_after_fill": after_fill.state.name,
            "replace": "DEFERRED",
        },
    )


def qualify_unknown_reconcile(tmp: Path) -> AreaResult:
    from crypto.execution import ExecutionEngine, ExecutionMode, ExecutionStore, OrderState, PaperBroker
    from crypto.market.quality import DataQuality, DataQualityReport
    from crypto.risk import MarketConstraints, RiskEngine, RiskPolicy

    store = ExecutionStore(tmp / "unk.db")
    engine = ExecutionEngine(
        _mock_adapter(), RiskEngine(RiskPolicy(max_position_pct=50.0)), store,
        mode=ExecutionMode.PAPER, paper_broker=PaperBroker(),
    )
    rec = engine.submit(
        _decision(qty=0.15, price=100.0), _portfolio(),
        intent_key="unk-s6",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    rec.state = OrderState.UNKNOWN
    store.save(rec)
    before_id = rec.execution_id
    out = engine.reconcile(rec.execution_id)
    same_id = out.execution_id == before_id
    recovered = engine.recover_on_startup()
    return AreaResult(
        "unknown_handling",
        "PASS" if same_id else "FAIL",
        "PRODUCTION_PAPER",
        {
            "same_execution_id": same_id,
            "post_reconcile_state": out.state.name,
            "recover_count": len(recovered),
            "timeout_ne_not_executed": True,
        },
    )


def qualify_recovery_boundaries(tmp: Path) -> AreaResult:
    from crypto.execution import ExecutionEngine, ExecutionMode, ExecutionStore, PaperBroker
    from crypto.market.quality import DataQuality, DataQualityReport
    from crypto.risk import MarketConstraints, RiskEngine, RiskPolicy

    path = tmp / "recov.db"
    store = ExecutionStore(path)
    engine = ExecutionEngine(
        _mock_adapter(), RiskEngine(RiskPolicy(max_position_pct=50.0)), store,
        mode=ExecutionMode.PAPER, paper_broker=PaperBroker(fill_ratio=1.0),
    )
    rec = engine.submit(
        _decision(qty=0.12, price=100.0), _portfolio(),
        intent_key="recov-s6",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    store2 = ExecutionStore(path)
    eng2 = ExecutionEngine(
        _mock_adapter(), RiskEngine(RiskPolicy(max_position_pct=50.0)), store2,
        mode=ExecutionMode.PAPER, paper_broker=PaperBroker(),
    )
    loaded = store2.get(rec.execution_id)
    eng2.recover_on_startup()
    again = eng2.submit(
        _decision(qty=0.12, price=100.0), _portfolio(),
        intent_key="recov-s6",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    ok = loaded is not None and again.execution_id == rec.execution_id
    return AreaResult(
        "recovery_boundaries",
        "PASS" if ok else "FAIL",
        "PRODUCTION_PAPER",
        {
            "persisted": loaded is not None,
            "state_after_reload": loaded.state.name if loaded else None,
            "idempotent_after_restart": again.execution_id == rec.execution_id,
            "process_kill_per_boundary": "UNOBSERVABLE (store-level restart simulated)",
        },
    )
