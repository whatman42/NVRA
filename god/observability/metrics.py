"""Phase 6C — N.U.N.G. operational metrics. Bounded counters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OperationalMetrics:
    cycles_started: int = 0
    cycles_completed: int = 0
    cycles_failed: int = 0
    cycles_abstained: int = 0
    snapshots_received: int = 0
    snapshots_valid: int = 0
    snapshots_invalid: int = 0
    partial_snapshots: int = 0
    stale_snapshots: int = 0
    unavailable_snapshots: int = 0
    provider_failures: int = 0
    retry_count: int = 0
    circuit_open_count: int = 0
    rate_limit_count: int = 0
    opportunities_selected: int = 0
    opportunities_rejected: int = 0
    no_valid_candidate: int = 0
    no_valid_opportunity: int = 0
    unknown_decisions: int = 0
    blocked_decisions: int = 0
    paper_cycles: int = 0
    paper_completed: int = 0
    paper_rejected: int = 0
    paper_reconciled: int = 0
    paper_corrupted: int = 0
    readiness_checks: int = 0
    readiness_passed: int = 0
    readiness_failed: int = 0

    def inc(self, name: str, n: int = 1) -> None:
        if not hasattr(self, name):
            return
        cur = getattr(self, name)
        if isinstance(cur, int):
            setattr(self, name, cur + n)

    def to_dict(self) -> dict[str, int]:
        return {k: v for k, v in self.__dict__.items() if isinstance(v, int)}

    def summary(self) -> dict[str, int]:
        return self.to_dict()
