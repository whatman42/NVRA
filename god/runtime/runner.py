"""CognitiveRuntimeRunner — N.U.N.G. operational cognitive cycles. No execution."""

from __future__ import annotations

from typing import Any, Optional

from god.data.ingestion import MarketDataIngestion
from god.data.models import IngestionStatus
from god.data.source import MarketDataSource
from god.data.bridge import run_cycle_from_source
from god.loop import CycleStatus

from .clock import Clock, SystemClock
from .freshness import assess_freshness
from .models import (
    FreshnessPolicy,
    FreshnessStatus,
    RuntimeConfig,
    RuntimeOutcome,
    RuntimeResult,
    RuntimeStatus,
)
from .recovery import RuntimeRecovery
from .scheduler import Scheduler
from .state import RuntimeStateStore


class CognitiveRuntimeRunner:
    """
    Orchestrates: source → ingest → freshness → cognitive loop → state.
    No pair/symbol/strategy parameters. No trade execution.
    """

    def __init__(
        self,
        source: MarketDataSource,
        *,
        config: Optional[RuntimeConfig] = None,
        clock: Optional[Clock] = None,
        strategy_registry: Any = None,
        policy_engine: Any = None,
        capital_engine: Any = None,
        drift_engine: Any = None,
        regime_engine: Any = None,
        reality_engine: Any = None,
        memory_store: Any = None,
    ) -> None:
        self.source = source
        self.config = config or RuntimeConfig()
        self.clock = clock or SystemClock()
        self.strategy_registry = strategy_registry
        self.policy_engine = policy_engine
        self.capital_engine = capital_engine
        self.drift_engine = drift_engine
        self.regime_engine = regime_engine
        self.reality_engine = reality_engine
        self.state = RuntimeStateStore(memory_store)
        self.scheduler = Scheduler(self.config, self.clock)
        self.recovery = RuntimeRecovery(memory_store)
        self._last_result: Optional[RuntimeResult] = None

    def run_once(self, *, force: bool = True) -> RuntimeResult:
        """Execute one cognitive cycle if scheduler allows (or force)."""
        if not self.scheduler.should_run(force=force):
            return RuntimeResult(
                status=RuntimeStatus.WAITING,
                outcome=RuntimeOutcome.WAITING,
                wait_seconds=self.scheduler.wait_duration(),
                next_run_at=self.scheduler.next_run_iso(),
                notes="interval_not_elapsed",
            )

        now = self.clock.now_iso()
        # Ingest
        ingestion = MarketDataIngestion(
            self.source,
            max_symbols=self.config.max_symbols,
            max_bars=self.config.max_bars,
            min_bars=self.config.min_bars,
            now_iso=now,
        )
        try:
            snap = ingestion.ingest()
        except Exception as exc:
            self.state.record_failure(
                at=now, outcome=RuntimeOutcome.FAILED, status=RuntimeStatus.FAILED
            )
            return RuntimeResult(
                status=RuntimeStatus.FAILED,
                outcome=RuntimeOutcome.FAILED,
                notes=f"ingest_error:{type(exc).__name__}",
            )

        if snap.ingestion_status == IngestionStatus.EMPTY:
            self.state.record_failure(
                at=now, outcome=RuntimeOutcome.NO_DATA, status=RuntimeStatus.BLOCKED
            )
            return RuntimeResult(
                status=RuntimeStatus.BLOCKED,
                outcome=RuntimeOutcome.NO_DATA,
                snapshot_id=snap.snapshot_id,
                notes="empty_universe_or_data",
            )

        if snap.ingestion_status in (
            IngestionStatus.NO_VALID_MARKET_DATA,
            IngestionStatus.INVALID_MARKET_DATA,
        ):
            self.state.record_failure(
                at=now,
                outcome=RuntimeOutcome.INVALID_DATA,
                status=RuntimeStatus.BLOCKED,
            )
            return RuntimeResult(
                status=RuntimeStatus.BLOCKED,
                outcome=RuntimeOutcome.INVALID_DATA,
                snapshot_id=snap.snapshot_id,
                notes=snap.ingestion_status.value,
            )

        # Freshness gate
        fresh_status, fresh_reason = assess_freshness(
            snap, self.config.freshness, now_iso=now
        )
        if fresh_status == FreshnessStatus.INVALID:
            self.state.record_failure(
                at=now,
                outcome=RuntimeOutcome.INVALID_DATA,
                status=RuntimeStatus.BLOCKED,
            )
            return RuntimeResult(
                status=RuntimeStatus.BLOCKED,
                outcome=RuntimeOutcome.INVALID_DATA,
                snapshot_id=snap.snapshot_id,
                notes=fresh_reason,
            )
        if fresh_status == FreshnessStatus.STALE and self.config.freshness.fail_on_stale:
            self.state.record_failure(
                at=now,
                outcome=RuntimeOutcome.STALE_DATA,
                status=RuntimeStatus.DEGRADED,
            )
            return RuntimeResult(
                status=RuntimeStatus.DEGRADED,
                outcome=RuntimeOutcome.STALE_DATA,
                snapshot_id=snap.snapshot_id,
                notes=fresh_reason,
            )
        if fresh_status == FreshnessStatus.UNKNOWN and self.config.freshness.require_timestamps:
            self.state.record_failure(
                at=now,
                outcome=RuntimeOutcome.UNKNOWN,
                status=RuntimeStatus.DEGRADED,
            )
            return RuntimeResult(
                status=RuntimeStatus.DEGRADED,
                outcome=RuntimeOutcome.UNKNOWN,
                snapshot_id=snap.snapshot_id,
                notes=fresh_reason,
            )

        # Cognitive cycle via 4L bridge
        try:
            snap2, cycle = run_cycle_from_source(
                self.source,
                strategy_registry=self.strategy_registry,
                policy_engine=self.policy_engine,
                capital_engine=self.capital_engine,
                drift_engine=self.drift_engine,
                regime_engine=self.regime_engine,
                reality_engine=self.reality_engine,
                max_matrix_cells=self.config.max_matrix_cells,
                max_attention=self.config.max_attention,
                max_symbols=self.config.max_symbols,
                max_bars=self.config.max_bars,
                min_bars=self.config.min_bars,
                now_iso=now,
            )
        except Exception as exc:
            self.state.record_failure(
                at=now, outcome=RuntimeOutcome.FAILED, status=RuntimeStatus.FAILED
            )
            return RuntimeResult(
                status=RuntimeStatus.FAILED,
                outcome=RuntimeOutcome.FAILED,
                snapshot_id=snap.snapshot_id,
                notes=f"loop_error:{type(exc).__name__}",
            )

        self.scheduler.mark_ran()

        if cycle is None:
            outcome = RuntimeOutcome.NO_DATA
            status = RuntimeStatus.BLOCKED
            result = RuntimeResult(
                status=status,
                outcome=outcome,
                snapshot_id=snap2.snapshot_id if snap2 else snap.snapshot_id,
                notes="no_cycle_from_snapshot",
            )
            self.state.record_failure(at=now, outcome=outcome, status=status)
            self._last_result = result
            return result

        outcome = self._map_cycle_outcome(cycle.status)
        status = (
            RuntimeStatus.WAITING
            if outcome
            in (
                RuntimeOutcome.SUCCESS,
                RuntimeOutcome.NO_VALID_OPPORTUNITY,
                RuntimeOutcome.NO_VALID_CANDIDATE,
                RuntimeOutcome.INSUFFICIENT_EVIDENCE,
            )
            else RuntimeStatus.DEGRADED
            if outcome == RuntimeOutcome.DEGRADED
            else RuntimeStatus.BLOCKED
            if outcome == RuntimeOutcome.BLOCKED
            else RuntimeStatus.WAITING
        )

        result = RuntimeResult(
            status=status,
            outcome=outcome,
            cycle_id=cycle.cycle_id,
            snapshot_id=snap2.snapshot_id if snap2 else snap.snapshot_id,
            discovery_result_id=cycle.discovery_result_id,
            selection_id=cycle.selection_id,
            attention_set_id=cycle.attention.set_id if cycle.attention else None,
            next_run_at=self.scheduler.next_run_iso(),
            wait_seconds=self.config.interval_seconds,
            notes="cognitive_cycle_complete",
            metadata={
                "cycle_status": cycle.status.value,
                "stages": list(cycle.stages_completed),
            },
        )
        if outcome in (
            RuntimeOutcome.SUCCESS,
            RuntimeOutcome.NO_VALID_OPPORTUNITY,
            RuntimeOutcome.NO_VALID_CANDIDATE,
            RuntimeOutcome.INSUFFICIENT_EVIDENCE,
        ):
            self.state.record_success(
                cycle_id=cycle.cycle_id,
                snapshot_id=result.snapshot_id,
                at=now,
                outcome=outcome,
            )
        else:
            self.state.record_failure(at=now, outcome=outcome, status=status)
        self._last_result = result
        return result

    def health(self) -> dict:
        return self.state.health.to_dict()

    def _map_cycle_outcome(self, status: CycleStatus) -> RuntimeOutcome:
        mapping = {
            CycleStatus.COMPLETE: RuntimeOutcome.SUCCESS,
            CycleStatus.ATTENTION: RuntimeOutcome.SUCCESS,
            CycleStatus.NO_VALID_OPPORTUNITY: RuntimeOutcome.NO_VALID_OPPORTUNITY,
            CycleStatus.INSUFFICIENT_EVIDENCE: RuntimeOutcome.INSUFFICIENT_EVIDENCE,
            CycleStatus.BLOCKED: RuntimeOutcome.BLOCKED,
            CycleStatus.CORRUPTED: RuntimeOutcome.CORRUPTED,
            CycleStatus.UNKNOWN: RuntimeOutcome.UNKNOWN,
        }
        return mapping.get(status, RuntimeOutcome.UNKNOWN)
