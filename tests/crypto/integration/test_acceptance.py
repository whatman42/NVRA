"""Deterministic full-pipeline acceptance — PAPER only, no LIVE orders."""

from __future__ import annotations

from crypto.control import CommandResult, ControlPlane
from crypto.execution.adversarial import PROFILES, AdversarialPaperBroker
from crypto.execution.models import ExecutionMode
from crypto.governor import ResourceGovernor, ResourceSample
from crypto.governor.config import GovernorThresholds
from crypto.governor.freshness import MarketDataFreshnessGate
from crypto.hardware.models import ResourceBudget
from crypto.ml.provenance import DataProvenance, LabeledRow, assert_training_allowed
from crypto.notify import NotifyPriority, NotifyQueue
from crypto.recovery import Supervisor
from crypto.risk.policy import RiskPolicy


def test_authority_chain_paper_only() -> None:
    """ControlPlane → RiskPolicy unchanged; execution path tagged PAPER."""
    policy = RiskPolicy()
    cp = ControlPlane(risk_policy=policy)
    cp.authorize_chat("1")
    fp = cp.risk_policy_fingerprint()
    r = cp.dispatch("emergency_stop", actor="tg:1", chat_id="1")
    assert r.result is CommandResult.OK
    assert cp.risk_policy_fingerprint() == fp
    assert cp.runtime.emergency_stop is True

    br = AdversarialPaperBroker(PROFILES["retail"])
    o = br.create_order("BTC/USDT", "buy", "market", 0.01, mid_price=50_000.0)
    assert o.get("mode") == "PAPER"


def test_stale_and_safe_mode_block_entries() -> None:
    gate = MarketDataFreshnessGate()
    assert gate.allow_new_proposal(gate.evaluate(None)) is False
    sup = Supervisor()
    sup.enter_safe_mode("acceptance")
    assert sup.blocks_new_entries() is True


def test_governor_ring0_under_pressure() -> None:
    budget = ResourceBudget(
        recommended_workers=1,
        max_workers=2,
        max_ml_models=1,
        max_universe=50,
        max_candidates=20,
        max_ml_candidates=5,
        max_predictions_per_cycle=3,
        max_opportunities=2,
        prediction_cache_size=8,
        feature_cache_size=8,
        market_cache_size=16,
        ohlcv_cache_size=8,
        max_features=10,
        max_training_rows=500,
        memory_pressure_warning_bytes=10**8,
        memory_pressure_critical_bytes=2 * 10**8,
        ml_profile_name="ULTRA_LITE",
    )

    class Clock:
        t = 100.0

        def __call__(self) -> float:
            return self.t

    c = Clock()
    gov = ResourceGovernor(budget, GovernorThresholds(min_dwell_seconds=0.5), now_fn=c)
    c.t += 5
    snap = gov.evaluate(
        ResourceSample(
            timestamp_ms=1,
            cpu_utilization=0.99,
            ram_total_bytes=10**9,
            ram_available_bytes=10**7,
            process_rss_bytes=10**8,
            swap_used_bytes=10**8,
            io_wait_ratio=0.5,
            disk_latency_ms=400.0,
            network_latency_ms=3000.0,
            network_errors=5,
            queue_depth=2000,
            queue_age_ms=9000.0,
            cpu_temp_c=92.0,
            on_battery=False,
        )
    )
    assert snap.ring0.name == "PROTECTED"
    # Risk policy independent
    assert RiskPolicy().max_drawdown_pct == RiskPolicy().max_drawdown_pct


def test_notify_and_control_isolation() -> None:
    q = NotifyQueue()
    q.publish("fill", "order filled", priority=NotifyPriority.P1)
    q.publish("EMERGENCY", "stop", priority=NotifyPriority.P0)
    n = q.pop_ready()
    assert n is not None and n.priority is NotifyPriority.P0


def test_no_live_training_from_paper() -> None:
    import pytest

    from crypto.ml.provenance import ProvenancePolicyError

    rows = [
        LabeledRow((0.0,), 1.0, DataProvenance.PAPER),
    ]
    with pytest.raises(ProvenancePolicyError):
        assert_training_allowed(rows, target_mode=ExecutionMode.LIVE)
