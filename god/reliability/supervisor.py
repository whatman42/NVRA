"""Phase 6E — N.U.N.G. reliability supervisor. Recovery ≠ Authorization."""

from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

from god.memory.database import utc_now
from god.observability import EventType, HealthState, ObservabilityService
from god.research.provenance import content_hash

from .backoff import BackoffPolicy
from .models import (
    FailureKind,
    FailureRecord,
    RecoveryState,
    classify_exception,
    is_recoverable,
    make_failure_id,
)

T = TypeVar("T")


class ReliabilitySupervisor:
    """
    Bounded recovery / crash-loop protection / graceful halt.
    Does not grant trading authority.
    """

    def __init__(
        self,
        *,
        backoff: Optional[BackoffPolicy] = None,
        observability: Optional[ObservabilityService] = None,
        max_failure_history: int = 100,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.backoff = backoff or BackoffPolicy()
        self.obs = observability or ObservabilityService()
        self.max_failure_history = max_failure_history
        self._sleep = sleep_fn or (lambda _d: None)
        self.state = RecoveryState.HEALTHY
        self.restart_count = 0
        self._failures: list[FailureRecord] = []
        self._halt_reason: str = ""

    def classify(self, exc: BaseException) -> FailureKind:
        return classify_exception(exc)

    def record_failure(
        self,
        kind: FailureKind,
        message: str,
        *,
        component: str = "",
        cycle_id: str = "",
    ) -> FailureRecord:
        payload = {
            "kind": kind.value,
            "message": message,
            "component": component,
            "cycle_id": cycle_id,
        }
        rec = FailureRecord(
            failure_id=make_failure_id(payload),
            kind=kind,
            message=message,
            content_hash=content_hash(payload),
            component=component,
            cycle_id=cycle_id,
            recoverable=is_recoverable(kind),
        )
        self._failures.append(rec)
        while len(self._failures) > self.max_failure_history:
            self._failures.pop(0)
        self.obs.emit(
            EventType.CYCLE_FAILED,
            cycle_id=cycle_id,
            message=f"{kind.value}:{message}",
        )
        return rec

    def run_with_recovery(
        self,
        fn: Callable[[], T],
        *,
        component: str = "runtime",
    ) -> tuple[Optional[T], Optional[FailureRecord]]:
        """
        Execute fn with bounded recoverable retries.
        Non-recoverable → FAIL_CLOSED immediately.
        Exhausted → HALTED.
        """
        if self.state == RecoveryState.HALTED:
            return None, self.record_failure(
                FailureKind.FATAL, "already_halted", component=component
            )

        attempts = 0
        last_fail: Optional[FailureRecord] = None
        while attempts <= self.backoff.max_attempts:
            try:
                result = fn()
                if self.state == RecoveryState.RECOVERING:
                    self.state = RecoveryState.HEALTHY
                    self.obs.emit(EventType.RECOVERY_COMPLETED, message=component)
                return result, None
            except Exception as exc:
                kind = self.classify(exc)
                last_fail = self.record_failure(
                    kind, str(exc) or type(exc).__name__, component=component
                )
                if not is_recoverable(kind):
                    self.state = RecoveryState.FAILED
                    if kind in (
                        FailureKind.CORRUPTION,
                        FailureKind.FATAL,
                        FailureKind.SECURITY_FAILURE,
                    ):
                        self.halt(f"non_recoverable:{kind.value}")
                    return None, last_fail
                if attempts >= self.backoff.max_attempts:
                    self.halt("retry_exhausted")
                    return None, last_fail
                self.state = RecoveryState.RECOVERING
                self.obs.emit(EventType.RECOVERY_STARTED, message=component)
                self._sleep(self.backoff.delay_for_attempt(attempts))
                attempts += 1
        self.halt("retry_exhausted")
        return None, last_fail

    def request_restart(self) -> bool:
        """Bounded restart counter. Returns False if crash-loop protected."""
        if self.state == RecoveryState.HALTED:
            return False
        self.restart_count += 1
        if self.restart_count > self.backoff.max_attempts:
            self.halt("crash_loop_protection")
            return False
        self.state = RecoveryState.RECOVERING
        self.obs.emit(EventType.RECOVERY_STARTED, message="restart")
        return True

    def halt(self, reason: str) -> None:
        self.state = RecoveryState.HALTED
        self._halt_reason = reason
        self.obs.record_component(
            "reliability",
            HealthState.UNAVAILABLE,
            reason_codes=(reason,),
        )
        self.obs.emit(EventType.SYSTEM_STOPPED, message=f"halted:{reason}")

    def graceful_shutdown(self) -> RecoveryState:
        """STOP → persist boundary → STOPPED semantics (no forced kill)."""
        if self.state == RecoveryState.HALTED:
            return self.state
        self.obs.emit(EventType.SYSTEM_STOPPED, message="graceful_shutdown")
        self.state = RecoveryState.HEALTHY  # clean stop, not failure
        # After clean shutdown, supervisor is idle-healthy for next start
        return self.state

    def startup_safe(self, *, config_valid: bool, state_hash_ok: bool) -> bool:
        """Mandatory startup checks. Fail-closed."""
        if not config_valid:
            self.halt("startup_config_invalid")
            return False
        if not state_hash_ok:
            self.halt("startup_state_corrupt")
            return False
        if self.state == RecoveryState.HALTED:
            return False
        self.state = RecoveryState.HEALTHY
        return True

    @property
    def halt_reason(self) -> str:
        return self._halt_reason

    def failure_history(self) -> list[FailureRecord]:
        return list(self._failures)
