"""AgentCore — closed-loop runtime skeleton.

Composes Observer / Decider / Executor / Measurer / Learner.
No hard-coded trading strategy. Default Decider always returns NO_ACTION
unless an explicit override is injected for tests.
"""

from __future__ import annotations

import time
from typing import Optional, Any, Callable

from god.memory.repositories import MemoryStore
from god.memory.models import (
    Observation as MemObservation,
    Decision as MemDecision,
    Trade as MemTrade,
    Position as MemPosition,
    Experience as MemExperience,
    AuditRecord,
)
from god.memory.database import utc_now

from god.execution.protocols import ExecutionProvider
from god.execution.null import NullExecutionProvider

from .models import (
    RuntimeObservation,
    RuntimeDecision,
    ExecutionRequest,
    ExecutionResult,
    Measurement,
    LearningResult,
    AccountState,
    MarketState,
    ActionType,
    LifecycleState,
    new_id,
)
from .lifecycle import DefaultLifecycleManager
from .errors import AgentError, ObservationError, DecisionError, ExecutionError
from .protocols import Observer, Decider, Executor, Measurer, Learner


# ── Default component implementations ────────────────────────────────────


class DefaultObserver:
    """Builds a RuntimeObservation from the ExecutionProvider."""

    def __init__(self, provider: ExecutionProvider, source: str = "agent") -> None:
        self.provider = provider
        self.source = source

    def observe(self) -> RuntimeObservation:
        account = self.provider.get_account_state()
        market = self.provider.get_market_state()
        positions = list(self.provider.get_positions())
        return RuntimeObservation.create(
            source=self.source,
            environment=self.provider.name,
            account_state=account,
            market_state=market,
            positions=positions,
            capabilities=(self.provider.name,),
        )


class StubDecider:
    """Phase-3 stub policy: always NO_ACTION.

    Real strategy intelligence is forbidden in Phase 3.
    Tests may inject a custom Decider that returns other actions.
    """

    def __init__(self, policy_version: str = "phase3-stub-v0") -> None:
        self.policy_version = policy_version

    def decide(self, observation: RuntimeObservation) -> RuntimeDecision:
        return RuntimeDecision.create(
            observation_id=observation.observation_id,
            action=ActionType.NO_ACTION,
            rationale="stub policy — no strategy intelligence in Phase 3",
            policy_version=self.policy_version,
            symbol=observation.market_state.symbol,
        )


class DefaultExecutor:
    """Translates RuntimeDecision → ExecutionRequest → provider.submit()."""

    def __init__(self, provider: ExecutionProvider) -> None:
        self.provider = provider

    def execute(self, decision: RuntimeDecision) -> ExecutionResult:
        req = ExecutionRequest.from_decision(decision)
        return self.provider.submit(req)


class DefaultMeasurer:
    def measure(
        self,
        decision: RuntimeDecision,
        result: ExecutionResult,
        latency_ms: float = 0.0,
    ) -> Measurement:
        return Measurement.from_result(decision, result, latency_ms=latency_ms)


class StubLearner:
    """Records an Experience row; does not update any model."""

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def learn(
        self,
        observation: RuntimeObservation,
        decision: RuntimeDecision,
        result: ExecutionResult,
        measurement: Measurement,
    ) -> LearningResult:
        exp = MemExperience.create(
            symbol=decision.symbol or observation.market_state.symbol,
            action=decision.action.value,
            market_state={
                "bid": observation.market_state.bid,
                "ask": observation.market_state.ask,
            },
            features={},
            policy_version=decision.policy_version,
            is_virtual=(observation.environment == "virtual"),
            trade_id=result.position_id,
            pnl=measurement.pnl,
            fees=measurement.fees,
            slippage=measurement.slippage,
            outcome="success" if result.success else "failure",
        )
        self.memory.add_experience(exp)
        return LearningResult.create(experiences_recorded=1)


# ── AgentCore ────────────────────────────────────────────────────────────


class AgentCore:
    """Closed-loop agent runtime.

    observe → decide → execute → measure → learn
    with persistent lifecycle and Memory/Audit integration.
    """

    def __init__(
        self,
        memory: MemoryStore,
        provider: Optional[ExecutionProvider] = None,
        observer: Optional[Observer] = None,
        decider: Optional[Decider] = None,
        executor: Optional[Executor] = None,
        measurer: Optional[Measurer] = None,
        learner: Optional[Learner] = None,
        agent_id: str = "default",
    ) -> None:
        self.memory = memory
        self.provider = provider or NullExecutionProvider()
        self.lifecycle = DefaultLifecycleManager(memory, agent_id=agent_id)
        self.agent_id = agent_id

        self.observer = observer or DefaultObserver(self.provider)
        self.decider = decider or StubDecider()
        self.executor = executor or DefaultExecutor(self.provider)
        self.measurer = measurer or DefaultMeasurer()
        self.learner = learner or StubLearner(memory)

    # ── public API matching the required contract ────────────────────────

    def observe(self) -> RuntimeObservation:
        self.lifecycle.transition(LifecycleState.OBSERVING, reason="observe()")
        try:
            obs = self.observer.observe()
            # Persist to memory
            mem_obs = MemObservation.create(
                observation_id=obs.observation_id,
                timestamp=obs.timestamp,
                symbol=obs.market_state.symbol,
                market_state={
                    "bid": obs.market_state.bid,
                    "ask": obs.market_state.ask,
                    "last": obs.market_state.last,
                    "account_balance": obs.account_state.balance,
                    "account_equity": obs.account_state.equity,
                    "positions_count": len(obs.positions),
                },
                features={},
                source=obs.source,
            )
            self.memory.add_observation(mem_obs)
            self.memory.append_audit(
                AuditRecord.create(
                    component="agent",
                    action="observe",
                    entity_type="observation",
                    entity_id=obs.observation_id,
                    new_state={"environment": obs.environment, "positions": len(obs.positions)},
                )
            )
            return obs
        except Exception as e:
            self.lifecycle.transition(LifecycleState.ERROR, reason=str(e))
            raise ObservationError(str(e)) from e

    def decide(self, observation: RuntimeObservation) -> RuntimeDecision:
        self.lifecycle.transition(LifecycleState.DECIDING, reason="decide()")
        try:
            decision = self.decider.decide(observation)
            mem_dec = MemDecision.create(
                decision_id=decision.decision_id,
                action=decision.action.value,
                observation_id=decision.observation_id,
                symbol=decision.symbol,
                volume=decision.volume,
                sl=decision.sl,
                tp=decision.tp,
                confidence=decision.confidence,
                policy_version=decision.policy_version,
                reasoning={"rationale": decision.rationale, "metadata": decision.metadata},
            )
            self.memory.add_decision(mem_dec)
            self.memory.append_audit(
                AuditRecord.create(
                    component="agent",
                    action="decide",
                    entity_type="decision",
                    entity_id=decision.decision_id,
                    new_state={"action": decision.action.value, "policy": decision.policy_version},
                )
            )
            return decision
        except Exception as e:
            self.lifecycle.transition(LifecycleState.ERROR, reason=str(e))
            raise DecisionError(str(e)) from e

    def execute(self, decision: RuntimeDecision) -> ExecutionResult:
        self.lifecycle.transition(LifecycleState.EXECUTING, reason="execute()")
        req = ExecutionRequest.from_decision(decision)
        self.lifecycle.set_pending_request(req.request_id)
        try:
            result = self.executor.execute(decision)
            # If the executor already created a request internally, prefer its request_id
            # but we still recorded ours as pending.
            if result.success and result.executed_action == ActionType.OPEN and result.position_id:
                # Persist virtual trade / position when applicable
                self._persist_execution(decision, result)
            self.memory.append_audit(
                AuditRecord.create(
                    component="agent",
                    action="execute",
                    entity_type="execution",
                    entity_id=result.request_id,
                    new_state={
                        "success": result.success,
                        "executed_action": result.executed_action.value,
                        "is_duplicate": result.is_duplicate,
                    },
                    reason=result.message,
                )
            )
            self.lifecycle.set_pending_request(None)
            return result
        except Exception as e:
            # Leave pending_request set so recovery can see it
            self.lifecycle.force_crash(reason=str(e))
            raise ExecutionError(str(e)) from e

    def measure(
        self,
        decision: RuntimeDecision,
        result: ExecutionResult,
        latency_ms: float = 0.0,
    ) -> Measurement:
        self.lifecycle.transition(LifecycleState.MEASURING, reason="measure()")
        m = self.measurer.measure(decision, result, latency_ms=latency_ms)
        self.memory.append_audit(
            AuditRecord.create(
                component="agent",
                action="measure",
                entity_type="measurement",
                entity_id=m.measurement_id,
                new_state={
                    "requested": m.requested_action.value,
                    "executed": m.executed_action.value,
                    "success": m.success,
                    "latency_ms": m.latency_ms,
                },
            )
        )
        return m

    def learn(
        self,
        observation: RuntimeObservation,
        decision: RuntimeDecision,
        result: ExecutionResult,
        measurement: Measurement,
    ) -> LearningResult:
        self.lifecycle.transition(LifecycleState.LEARNING, reason="learn()")
        lr = self.learner.learn(observation, decision, result, measurement)
        self.memory.append_audit(
            AuditRecord.create(
                component="agent",
                action="learn",
                entity_type="learning",
                entity_id=lr.learning_id,
                new_state={"experiences_recorded": lr.experiences_recorded},
            )
        )
        self.lifecycle.transition(LifecycleState.READY, reason="cycle complete")
        return lr

    def step(self) -> dict:
        """Run one full observe→decide→execute→measure→learn cycle.

        Returns a summary dict useful for tests and diagnostics.
        """
        self.lifecycle.ensure_ready()
        t0 = time.perf_counter()
        obs = self.observe()
        decision = self.decide(obs)
        result = self.execute(decision)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        measurement = self.measure(decision, result, latency_ms=latency_ms)
        learning = self.learn(obs, decision, result, measurement)
        return {
            "observation_id": obs.observation_id,
            "decision_id": decision.decision_id,
            "action": decision.action.value,
            "executed_action": result.executed_action.value,
            "success": result.success,
            "is_duplicate": result.is_duplicate,
            "measurement_id": measurement.measurement_id,
            "learning_id": learning.learning_id,
            "latency_ms": latency_ms,
            "state": self.lifecycle.state.value,
        }

    def recover(self) -> dict:
        """Crash recovery: drive lifecycle and call provider.reconcile()."""
        self.lifecycle.recover()
        summary = self.provider.reconcile()
        self.memory.append_audit(
            AuditRecord.create(
                component="agent",
                action="recover",
                entity_type="lifecycle",
                entity_id=self.agent_id,
                new_state=summary,
                reason="recovery + reconcile",
            )
        )
        return summary

    # ── helpers ──────────────────────────────────────────────────────────

    def _persist_execution(self, decision: RuntimeDecision, result: ExecutionResult) -> None:
        if not result.position_id:
            return
        is_virtual = self.provider.name == "virtual"
        trade = MemTrade.create(
            symbol=decision.symbol or "UNKNOWN",
            side=decision.side or "BUY",
            volume=result.volume or 0.0,
            decision_id=decision.decision_id,
            entry_price=result.fill_price,
            status="OPEN",
            broker_ticket=result.order_id,
            is_virtual=is_virtual,
            fees=result.fees,
            slippage=result.slippage,
            metadata={"request_id": result.request_id},
        )
        # Use result.position_id as trade_id for correlation when possible
        trade.trade_id = result.position_id
        self.memory.upsert_trade(trade)

        pos = MemPosition.create(
            symbol=decision.symbol or "UNKNOWN",
            side=decision.side or "BUY",
            volume=result.volume or 0.0,
            entry_price=result.fill_price,
            current_price=result.fill_price,
            status="OPEN",
            broker_ticket=result.order_id,
            is_virtual=is_virtual,
        )
        pos.position_id = result.position_id
        self.memory.upsert_position(pos)
