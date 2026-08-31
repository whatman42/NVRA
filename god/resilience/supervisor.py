"""RuntimeSupervisor — thin failure classification & safe continuation for N.U.N.G."""

from __future__ import annotations

from typing import Any, Optional

from god.research.provenance import content_hash
from god.memory.database import utc_now
from god.runtime import (
    CognitiveRuntimeRunner,
    RuntimeOutcome,
    RuntimeResult,
    RuntimeStatus,
)

from .health import ResilienceHealth
from .journal import RuntimeJournal
from .models import (
    FailureClass,
    JournalEventType,
    PersistedCycleRecord,
    RecoveryState,
    ResilienceConfig,
    build_resilience_provenance,
    make_record_hash,
)
from .recovery import ResilienceRecovery
from .store import InMemoryRuntimeStateStore


class RuntimeSupervisor:
    """
    Trigger runtime, classify failures, persist, prevent unsafe reuse.
    Does NOT contain discovery/selection/fusion business logic.
    """

    def __init__(
        self,
        runner: CognitiveRuntimeRunner,
        *,
        config: Optional[ResilienceConfig] = None,
        memory_store: Any = None,
    ) -> None:
        self.runner = runner
        self.config = config or ResilienceConfig()
        self.store = InMemoryRuntimeStateStore(self.config, memory_store)
        self.journal = RuntimeJournal(self.config, memory_store)
        self.recovery = ResilienceRecovery(self.store)
        self.health = ResilienceHealth()
        self._completed_fingerprints: dict[str, str] = {}

    def run_supervised(self, *, force: bool = True) -> RuntimeResult:
        # Fingerprint from source universe for idempotency key attempt
        try:
            uni = tuple(self.runner.source.fetch_universe())
        except Exception:
            uni = ()
        fingerprint = content_hash(
            {
                "universe": list(uni),
                "v": self.config.runtime_version,
            }
        )

        # RETURN_EXISTING for successful same fingerprint
        if fingerprint in self._completed_fingerprints:
            cid = self._completed_fingerprints[fingerprint]
            insp = self.recovery.inspect(cid)
            if insp.get("action") == "RETURN_EXISTING":
                rec = self.store.load(cid)
                return RuntimeResult(
                    status=RuntimeStatus.WAITING,
                    outcome=RuntimeOutcome.SUCCESS
                    if rec and rec.outcome == "SUCCESS"
                    else RuntimeOutcome(rec.outcome)
                    if rec and rec.outcome in [o.value for o in RuntimeOutcome]
                    else RuntimeOutcome.SUCCESS,
                    cycle_id=cid,
                    snapshot_id=rec.snapshot_id if rec else None,
                    notes="RETURN_EXISTING",
                )

        cycle_token = "sup-" + content_hash({"f": fingerprint, "t": utc_now()})[:16]
        self.journal.append(cycle_token, JournalEventType.CYCLE_STARTED)

        attempts = 0
        last_result: Optional[RuntimeResult] = None
        while attempts <= self.config.max_retries:
            attempts += 1
            try:
                result = self.runner.run_once(force=force)
            except Exception as exc:
                fc = FailureClass.DATA_SOURCE_FAILURE
                if attempts <= self.config.max_retries:
                    continue  # retryable
                self._record_failure(cycle_token, None, fc, str(type(exc).__name__))
                return RuntimeResult(
                    status=RuntimeStatus.FAILED,
                    outcome=RuntimeOutcome.FAILED,
                    notes=f"source_or_runner:{type(exc).__name__}",
                )

            last_result = result
            self.journal.append(
                cycle_token,
                JournalEventType.SNAPSHOT_ACQUIRED,
                {"snapshot_id": result.snapshot_id},
            )

            # Non-retryable outcomes
            if result.outcome in (
                RuntimeOutcome.INVALID_DATA,
                RuntimeOutcome.CORRUPTED,
                RuntimeOutcome.BLOCKED,
            ):
                fc = self._map_failure(result.outcome)
                self._record_failure(
                    result.cycle_id or cycle_token,
                    result.snapshot_id,
                    fc,
                    result.notes,
                    outcome=result.outcome.value,
                )
                return result

            if result.outcome == RuntimeOutcome.STALE_DATA:
                self.health.consecutive_stale_data += 1
                self._record_failure(
                    result.cycle_id or cycle_token,
                    result.snapshot_id,
                    FailureClass.STALE_DATA,
                    result.notes,
                    outcome=result.outcome.value,
                    state=RecoveryState.DEGRADED,
                )
                return result

            if result.outcome == RuntimeOutcome.FAILED and attempts <= self.config.max_retries:
                continue

            # Success / abstention paths — persist as COMPLETED (valid cognitive outcomes)
            cid = result.cycle_id or cycle_token
            state = RecoveryState.COMPLETED
            if result.outcome in (
                RuntimeOutcome.NO_DATA,
                RuntimeOutcome.NO_VALID_CANDIDATE,
                RuntimeOutcome.NO_VALID_OPPORTUNITY,
                RuntimeOutcome.INSUFFICIENT_EVIDENCE,
                RuntimeOutcome.UNKNOWN,
                RuntimeOutcome.SUCCESS,
                RuntimeOutcome.WAITING,
            ):
                rec = self._make_record(
                    cid,
                    result.snapshot_id,
                    state,
                    result.outcome.value,
                    fingerprint,
                    FailureClass.NONE,
                )
                self.store.save(rec)
                self.journal.append(
                    cid, JournalEventType.CYCLE_COMPLETED, {"outcome": result.outcome.value}
                )
                self.health.last_successful_cycle = cid
                self.health.last_snapshot = result.snapshot_id
                self.health.consecutive_failures = 0
                self.health.cycles_recorded += 1
                if result.outcome in (
                    RuntimeOutcome.SUCCESS,
                    RuntimeOutcome.NO_VALID_OPPORTUNITY,
                    RuntimeOutcome.NO_VALID_CANDIDATE,
                    RuntimeOutcome.INSUFFICIENT_EVIDENCE,
                ):
                    self._completed_fingerprints[fingerprint] = cid
                return result

            # other
            self._record_failure(
                cid,
                result.snapshot_id,
                FailureClass.UNKNOWN_FAILURE,
                result.notes,
                outcome=result.outcome.value,
            )
            return result

        if last_result:
            return last_result
        return RuntimeResult(
            status=RuntimeStatus.FAILED,
            outcome=RuntimeOutcome.FAILED,
            notes="max_retries_exceeded",
        )

    def inspect(self, cycle_id: str) -> dict[str, Any]:
        self.health.recovery_count += 1
        self.journal.append(cycle_id, JournalEventType.RECOVERY_STARTED)
        out = self.recovery.inspect(cycle_id)
        self.journal.append(
            cycle_id, JournalEventType.RECOVERY_COMPLETED, {"status": out.get("status")}
        )
        return out

    def health_dict(self) -> dict[str, Any]:
        return self.health.to_dict()

    def _map_failure(self, outcome: RuntimeOutcome) -> FailureClass:
        return {
            RuntimeOutcome.INVALID_DATA: FailureClass.DATA_VALIDATION_FAILURE,
            RuntimeOutcome.STALE_DATA: FailureClass.STALE_DATA,
            RuntimeOutcome.CORRUPTED: FailureClass.CORRUPTED_STATE,
            RuntimeOutcome.NO_DATA: FailureClass.DATA_SOURCE_FAILURE,
            RuntimeOutcome.FAILED: FailureClass.COGNITIVE_FAILURE,
        }.get(outcome, FailureClass.UNKNOWN_FAILURE)

    def _make_record(
        self,
        cycle_id: str,
        snapshot_id: Optional[str],
        state: RecoveryState,
        outcome: str,
        fingerprint: str,
        failure_class: FailureClass,
    ) -> PersistedCycleRecord:
        now = utc_now()
        body = {
            "cycle_id": cycle_id,
            "snapshot_id": snapshot_id,
            "recovery_state": state.value,
            "outcome": outcome,
            "runtime_version": self.config.runtime_version,
            "fingerprint": fingerprint,
        }
        return PersistedCycleRecord(
            cycle_id=cycle_id,
            snapshot_id=snapshot_id,
            recovery_state=state,
            outcome=outcome,
            content_hash=make_record_hash(body),
            created_at=now,
            updated_at=now,
            runtime_version=self.config.runtime_version,
            fingerprint=fingerprint,
            failure_class=failure_class,
            provenance=build_resilience_provenance(body),
        )

    def _record_failure(
        self,
        cycle_id: str,
        snapshot_id: Optional[str],
        fc: FailureClass,
        notes: str,
        *,
        outcome: str = "FAILED",
        state: RecoveryState = RecoveryState.FAILED,
    ) -> None:
        fp = content_hash({"c": cycle_id, "n": notes})
        rec = self._make_record(cycle_id, snapshot_id, state, outcome, fp, fc)
        self.store.save(rec)
        self.journal.append(
            cycle_id, JournalEventType.CYCLE_FAILED, {"failure_class": fc.value}
        )
        self.health.last_failed_cycle = cycle_id
        if fc == FailureClass.CORRUPTED_STATE:
            self.health.last_corrupted_cycle = cycle_id
        self.health.consecutive_failures += 1
        self.health.cycles_recorded += 1
