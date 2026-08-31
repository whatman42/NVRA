"""Phase 3 acceptance tests — Agent Skeleton.

Covers:
- lifecycle
- typed observation / decision
- ExecutionProvider (Null + Virtual)
- request idempotency
- measurement
- learning interface
- Memory + audit integration
- restart / recovery
- deterministic behaviour
- failure injection
- no real broker
- no hard-coded trading strategy (stub always NO_ACTION by default)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from god.memory.database import Database
from god.memory.repositories import MemoryStore
from god.memory.models import AuditRecord

from god.agent import (
    AgentCore,
    LifecycleState,
    ActionType,
    RuntimeDecision,
    RuntimeObservation,
    ExecutionRequest,
    StubDecider,
    DefaultObserver,
)
from god.agent.errors import InvalidStateError
from god.agent.models import AccountState, MarketState
from god.execution import NullExecutionProvider, VirtualExecutionProvider


# ── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "agent_test.db")


@pytest.fixture
def memory(db_path):
    db = Database(db_path)
    store = MemoryStore(db)
    yield store
    db.close()


@pytest.fixture
def null_provider():
    return NullExecutionProvider()


@pytest.fixture
def virtual_provider():
    return VirtualExecutionProvider(initial_balance=10_000.0, bid=1.1000, ask=1.1002)


# ── Lifecycle ────────────────────────────────────────────────────────────


def test_lifecycle_bootstrap(memory):
    agent = AgentCore(memory=memory)
    assert agent.lifecycle.state == LifecycleState.CREATED
    agent.lifecycle.ensure_ready()
    assert agent.lifecycle.state == LifecycleState.READY


def test_lifecycle_invalid_transition(memory):
    agent = AgentCore(memory=memory)
    agent.lifecycle.ensure_ready()
    with pytest.raises(InvalidStateError):
        agent.lifecycle.transition(LifecycleState.LEARNING)  # READY → LEARNING illegal


def test_lifecycle_full_cycle_states(memory, null_provider):
    agent = AgentCore(memory=memory, provider=null_provider)
    agent.lifecycle.ensure_ready()
    summary = agent.step()
    assert summary["state"] == LifecycleState.READY.value
    assert summary["action"] == ActionType.NO_ACTION.value
    assert summary["success"] is True


def test_lifecycle_persists_across_instances(memory, null_provider):
    a1 = AgentCore(memory=memory, provider=null_provider)
    a1.lifecycle.ensure_ready()
    a1.lifecycle.transition(LifecycleState.OBSERVING, reason="test")
    # new instance, same DB
    a2 = AgentCore(memory=memory, provider=null_provider)
    assert a2.lifecycle.state == LifecycleState.OBSERVING


# ── Typed Observation / Decision ─────────────────────────────────────────


def test_typed_observation(memory, virtual_provider):
    agent = AgentCore(memory=memory, provider=virtual_provider)
    agent.lifecycle.ensure_ready()
    obs = agent.observe()
    assert isinstance(obs, RuntimeObservation)
    assert obs.observation_id
    assert obs.environment == "virtual"
    assert obs.account_state.balance == 10_000.0
    assert obs.market_state.bid == 1.1000
    # persisted
    mem_obs = memory.get_observation(obs.observation_id)
    assert mem_obs is not None
    assert mem_obs.observation_id == obs.observation_id


def test_typed_decision_stub_no_action(memory, null_provider):
    agent = AgentCore(memory=memory, provider=null_provider)
    agent.lifecycle.ensure_ready()
    obs = agent.observe()
    decision = agent.decide(obs)
    assert decision.action == ActionType.NO_ACTION
    assert "stub" in decision.rationale.lower() or "no strategy" in decision.rationale.lower()
    assert decision.policy_version.startswith("phase3")
    mem_dec = memory.get_decision(decision.decision_id)
    assert mem_dec is not None
    assert mem_dec.action == "NO_ACTION"


def test_no_hardcoded_trading_strategy_in_stub():
    """Sanity: StubDecider source does not contain classic indicator rules."""
    import inspect
    import re
    from god.agent.core import StubDecider
    src = inspect.getsource(StubDecider)
    # Word-boundary checks so substrings like "version" do not false-positive on "RSI"
    forbidden_patterns = [
        r"\bRSI\b", r"\bADX\b", r"\bMACD\b", r"\bbollinger\b",
        r"moving\s+average", r"confidence\s*>", r"\bRRR\b",
    ]
    for pat in forbidden_patterns:
        assert re.search(pat, src, re.IGNORECASE) is None, f"forbidden pattern {pat} found in StubDecider"


# ── Null Execution ───────────────────────────────────────────────────────


def test_null_provider_noop(null_provider):
    req = ExecutionRequest(
        request_id="r1",
        decision_id="d1",
        action=ActionType.NO_ACTION,
    )
    res = null_provider.submit(req)
    assert res.success is True
    assert res.executed_action == ActionType.NO_ACTION
    assert res.is_duplicate is False


def test_null_provider_refuses_open(null_provider):
    req = ExecutionRequest(
        request_id="r2",
        decision_id="d2",
        action=ActionType.OPEN,
        symbol="EURUSD",
        volume=0.1,
        side="BUY",
    )
    res = null_provider.submit(req)
    assert res.success is False
    assert "refuses" in res.message.lower() or "null" in res.message.lower()


def test_null_idempotency(null_provider):
    req = ExecutionRequest(
        request_id="idem-null-1",
        decision_id="d3",
        action=ActionType.NO_ACTION,
    )
    r1 = null_provider.submit(req)
    r2 = null_provider.submit(req)
    assert r1.is_duplicate is False
    assert r2.is_duplicate is True
    assert r2.request_id == r1.request_id
    assert r2.success == r1.success


# ── Virtual Execution ────────────────────────────────────────────────────


def test_virtual_open_close(virtual_provider):
    open_req = ExecutionRequest(
        request_id="vo1",
        decision_id="d-open",
        action=ActionType.OPEN,
        symbol="EURUSD",
        volume=0.1,
        side="BUY",
    )
    r_open = virtual_provider.submit(open_req)
    assert r_open.success is True
    assert r_open.executed_action == ActionType.OPEN
    assert r_open.position_id is not None
    assert r_open.fill_price == pytest.approx(1.1002)  # ask

    positions = virtual_provider.get_positions()
    assert len(positions) == 1
    assert positions[0]["side"] == "BUY"

    close_req = ExecutionRequest(
        request_id="vc1",
        decision_id="d-close",
        action=ActionType.CLOSE,
        position_id=r_open.position_id,
    )
    r_close = virtual_provider.submit(close_req)
    assert r_close.success is True
    assert r_close.executed_action == ActionType.CLOSE
    assert len(virtual_provider.get_positions()) == 0


def test_virtual_idempotency_open(virtual_provider):
    req = ExecutionRequest(
        request_id="videm-1",
        decision_id="d-idem",
        action=ActionType.OPEN,
        symbol="EURUSD",
        volume=0.05,
        side="SELL",
    )
    r1 = virtual_provider.submit(req)
    r2 = virtual_provider.submit(req)
    assert r1.success is True
    assert r2.is_duplicate is True
    # only one position created
    assert len(virtual_provider.get_positions()) == 1


def test_virtual_modify(virtual_provider):
    open_req = ExecutionRequest(
        request_id="vm-open",
        decision_id="d",
        action=ActionType.OPEN,
        symbol="EURUSD",
        volume=0.01,
        side="BUY",
    )
    r = virtual_provider.submit(open_req)
    mod = ExecutionRequest(
        request_id="vm-mod",
        decision_id="d2",
        action=ActionType.MODIFY,
        position_id=r.position_id,
        sl=1.0900,
        tp=1.1200,
    )
    rm = virtual_provider.submit(mod)
    assert rm.success is True
    pos = virtual_provider.get_positions()[0]
    assert pos["sl"] == 1.0900
    assert pos["tp"] == 1.1200


def test_virtual_account_state(virtual_provider):
    acc = virtual_provider.get_account_state()
    assert acc.balance == 10_000.0
    assert acc.equity == 10_000.0


# ── Measurement & Learning ───────────────────────────────────────────────


def test_measurement_and_learning(memory, null_provider):
    agent = AgentCore(memory=memory, provider=null_provider)
    agent.lifecycle.ensure_ready()
    obs = agent.observe()
    decision = agent.decide(obs)
    result = agent.execute(decision)
    m = agent.measure(decision, result, latency_ms=1.5)
    assert m.requested_action == ActionType.NO_ACTION
    assert m.executed_action == ActionType.NO_ACTION
    assert m.success is True
    assert m.latency_ms == 1.5
    lr = agent.learn(obs, decision, result, m)
    assert lr.experiences_recorded == 1
    exps = memory.list_experiences(limit=5)
    assert len(exps) >= 1


# ── Full step + Memory / Audit ───────────────────────────────────────────


def test_full_step_audit_trail(memory, virtual_provider):
    agent = AgentCore(memory=memory, provider=virtual_provider)
    summary = agent.step()
    assert summary["success"] is True
    audits = memory.list_audit(limit=50)
    actions = {a.action for a in audits}
    assert "transition" in actions or "observe" in actions
    # at least observe / decide / execute / measure / learn appear
    component_actions = {(a.component, a.action) for a in audits}
    assert any(a == "observe" for _, a in component_actions)
    assert any(a == "decide" for _, a in component_actions)


def test_step_with_custom_open_decider(memory, virtual_provider):
    """Inject a test-only Decider that returns OPEN — proves extensibility
    without hard-coding strategy into AgentCore.
    """

    class OpenOnceDecider:
        def __init__(self):
            self.called = False

        def decide(self, observation: RuntimeObservation) -> RuntimeDecision:
            if not self.called:
                self.called = True
                return RuntimeDecision.create(
                    observation_id=observation.observation_id,
                    action=ActionType.OPEN,
                    rationale="test-only injected decision",
                    symbol=observation.market_state.symbol or "EURUSD",
                    volume=0.01,
                    side="BUY",
                    policy_version="test-open-v0",
                )
            return RuntimeDecision.create(
                observation_id=observation.observation_id,
                action=ActionType.NO_ACTION,
                rationale="already opened",
            )

    agent = AgentCore(
        memory=memory,
        provider=virtual_provider,
        decider=OpenOnceDecider(),
    )
    s1 = agent.step()
    assert s1["action"] == ActionType.OPEN.value
    assert s1["success"] is True
    assert len(virtual_provider.get_positions()) == 1

    s2 = agent.step()
    assert s2["action"] == ActionType.NO_ACTION.value


# ── Recovery ─────────────────────────────────────────────────────────────


def test_recovery_after_crash(memory, virtual_provider):
    agent = AgentCore(memory=memory, provider=virtual_provider)
    agent.lifecycle.ensure_ready()
    agent.lifecycle.force_crash(reason="simulated process kill during EXECUTING")
    assert agent.lifecycle.state == LifecycleState.CRASH

    summary = agent.recover()
    assert agent.lifecycle.state == LifecycleState.READY
    assert summary["provider"] == "virtual"
    assert "open_positions" in summary


def test_recovery_clears_pending_request(memory, null_provider):
    agent = AgentCore(memory=memory, provider=null_provider)
    agent.lifecycle.ensure_ready()
    agent.lifecycle.set_pending_request("pending-xyz")
    agent.lifecycle.force_crash(reason="kill")
    agent.recover()
    assert agent.lifecycle.get_pending_request() is None
    assert agent.lifecycle.state == LifecycleState.READY


def test_restart_persistence_of_state(memory, null_provider):
    a1 = AgentCore(memory=memory, provider=null_provider, agent_id="A")
    a1.lifecycle.ensure_ready()
    a1.lifecycle.transition(LifecycleState.OBSERVING, reason="mid-cycle")
    # simulate process death → new AgentCore
    a2 = AgentCore(memory=memory, provider=null_provider, agent_id="A")
    assert a2.lifecycle.state == LifecycleState.OBSERVING
    # recovery path still works from non-CRASH if we force
    a2.lifecycle.force_crash(reason="restart recovery test")
    a2.recover()
    assert a2.lifecycle.state == LifecycleState.READY


# ── Failure injection ────────────────────────────────────────────────────


def test_failure_injection_on_execute(memory, null_provider):
    class BoomExecutor:
        def execute(self, decision):
            raise RuntimeError("injected failure")

    agent = AgentCore(
        memory=memory,
        provider=null_provider,
        executor=BoomExecutor(),
    )
    agent.lifecycle.ensure_ready()
    obs = agent.observe()
    decision = agent.decide(obs)
    with pytest.raises(Exception):
        agent.execute(decision)
    assert agent.lifecycle.state == LifecycleState.CRASH


def test_provider_reconcile_after_failure(virtual_provider):
    # open one position, then reconcile should report it
    req = ExecutionRequest(
        request_id="fr1",
        decision_id="d",
        action=ActionType.OPEN,
        symbol="EURUSD",
        volume=0.01,
        side="BUY",
    )
    virtual_provider.submit(req)
    rec = virtual_provider.reconcile()
    assert rec["open_positions"] == 1
    assert rec["seen_requests"] >= 1


# ── Determinism / no broker ──────────────────────────────────────────────


def test_no_real_broker_connection():
    """Null and Virtual must not import or call real MT*/socket broker code."""
    import god.execution.null as null_mod
    import god.execution.virtual as virt_mod
    import inspect
    for mod in (null_mod, virt_mod):
        src = inspect.getsource(mod)
        for banned in ("MetaTrader", "socket.connect", "zmq", "mt5.", "mt4."):
            assert banned.lower() not in src.lower()


def test_step_deterministic_with_null(memory, null_provider):
    agent = AgentCore(memory=memory, provider=null_provider)
    s1 = agent.step()
    s2 = agent.step()
    # both succeed with NO_ACTION
    assert s1["action"] == s2["action"] == ActionType.NO_ACTION.value
    assert s1["success"] is True and s2["success"] is True


def test_agent_core_not_monolith():
    """Ensure modules are split as required (no single giant agent.py)."""
    from pathlib import Path
    import god.agent as agent_pkg
    pkg_dir = Path(agent_pkg.__file__).parent
    expected = {"core.py", "models.py", "protocols.py", "state.py", "lifecycle.py", "errors.py"}
    present = {p.name for p in pkg_dir.iterdir() if p.suffix == ".py"}
    assert expected.issubset(present)


def test_execution_package_split():
    from pathlib import Path
    import god.execution as ex_pkg
    pkg_dir = Path(ex_pkg.__file__).parent
    expected = {"protocols.py", "null.py", "virtual.py"}
    present = {p.name for p in pkg_dir.iterdir() if p.suffix == ".py"}
    assert expected.issubset(present)
