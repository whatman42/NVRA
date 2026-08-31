"""SAFE MODE controller — conservative operation without mutating RiskPolicy."""

from __future__ import annotations

from dataclasses import dataclass, field

from crypto.recovery.events import RecoveryEvent, make_event


@dataclass
class SafeModeController:
    active: bool = False
    reason: str = ""
    entered_at_mono: float | None = None
    events: list[RecoveryEvent] = field(default_factory=list)

    def enter(self, reason: str, *, mono: float) -> None:
        if self.active:
            return
        self.active = True
        self.reason = reason
        self.entered_at_mono = mono
        self.events.append(make_event("SAFE_MODE_ENTERED", "supervisor", reason))

    def try_exit(
        self,
        *,
        components_healthy: bool,
        exchange_ok: bool,
        reconciliation_ok: bool,
        execution_consistent: bool,
        market_data_fresh: bool,
        no_unresolved_critical: bool,
        mono: float,
    ) -> bool:
        """Exit only when all gates pass. No automatic exit on process start alone."""
        if not self.active:
            return True
        if not all(
            (
                components_healthy,
                exchange_ok,
                reconciliation_ok,
                execution_consistent,
                market_data_fresh,
                no_unresolved_critical,
            )
        ):
            return False
        self.active = False
        self.reason = ""
        self.events.append(make_event("SAFE_MODE_EXITED", "supervisor", "all gates passed"))
        return True

    def blocks_new_entries(self) -> bool:
        return self.active

    def blocks_ml_scanner(self) -> bool:
        return self.active

    def blocks_unknown_resubmit(self) -> bool:
        return True  # always — even outside safe mode
