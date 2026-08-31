"""ProductionGate — LIVE blocked unless all critical checks pass.

CI never places LIVE orders. Operator must obtain GO before any canary.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from crypto.execution.models import ExecutionMode
from crypto.production.canary import CanaryState
from crypto.production.limits import MicroCapitalLimits, clamp_to_hard_ceiling
from crypto.production.profile import ExecutionProfiler


class GateSeverity(Enum):
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


class LiveDecision(Enum):
    GO = auto()
    NO_GO = auto()
    NOT_VERIFIED = auto()  # software green, production exchange not exercised


@dataclass(frozen=True, slots=True)
class GateCheck:
    name: str
    passed: bool
    severity: GateSeverity
    detail: str = ""


@dataclass
class ProductionGateReport:
    checks: list[GateCheck] = field(default_factory=list)
    live_decision: LiveDecision = LiveDecision.NO_GO
    software_green: bool = False
    production_live_verified: bool = False
    micro_capital: MicroCapitalLimits = field(default_factory=MicroCapitalLimits)
    canary: CanaryState = field(default_factory=CanaryState)
    build_hash: str = ""
    timestamp_ms: int = 0

    @property
    def critical_failures(self) -> list[GateCheck]:
        return [c for c in self.checks if not c.passed and c.severity is GateSeverity.CRITICAL]

    def summary_lines(self) -> list[str]:
        lines = [
            f"SOFTWARE: {'GREEN' if self.software_green else 'NOT GREEN'}",
            f"PRODUCTION LIVE: {'GO' if self.live_decision is LiveDecision.GO else self.live_decision.name}",
            f"build_hash={self.build_hash or 'unknown'}",
            f"micro_capital.enabled={self.micro_capital.enabled}",
        ]
        for c in self.checks:
            mark = "OK" if c.passed else "FAIL"
            lines.append(f"  [{mark}] {c.name}: {c.detail or c.severity.name}")
        return lines


# Injected probes — CI supplies mocks; production supplies real adapters
ConnectivityProbe = Callable[[], bool]
PermissionProbe = Callable[[], dict[str, str]]  # trading/withdrawal/unknown
IntegrityProbe = Callable[[], bool]


@dataclass
class ProductionGate:
    """Evaluates whether LIVE may be enabled. Default remains PAPER."""

    micro_capital: MicroCapitalLimits = field(default_factory=MicroCapitalLimits)
    expected_build_hash: str | None = None
    executable_path: Path | None = None
    connectivity: ConnectivityProbe | None = None
    permissions: PermissionProbe | None = None
    db_integrity: IntegrityProbe | None = None
    model_ok: IntegrityProbe | None = None
    recovery_ok: IntegrityProbe | None = None
    governor_ok: IntegrityProbe | None = None
    risk_ok: IntegrityProbe | None = None
    control_ok: IntegrityProbe | None = None
    time_skew_ms: int | None = None
    max_time_skew_ms: int = 5000
    withdrawal_status: str = "DISABLED"  # DISABLED | ENABLED | UNKNOWN
    unresolved_unknown: bool = False
    reconciliation_mismatch: bool = False
    emergency_stop_tested: bool = False
    canary_round_trip_ok: bool = False
    profiler: ExecutionProfiler = field(default_factory=ExecutionProfiler)
    force_live_flag: bool = False  # intentionally ignored for hash bypass

    def compute_build_hash(self, path: Path | None = None) -> str:
        target = path or self.executable_path
        if target is None or not Path(target).is_file():
            return ""
        h = hashlib.sha256()
        with open(target, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def evaluate(self, *, exchange_verified: bool = False) -> ProductionGateReport:
        limits = clamp_to_hard_ceiling(self.micro_capital)
        limits.validate()
        report = ProductionGateReport(
            micro_capital=limits,
            timestamp_ms=int(time.time() * 1000),
        )
        checks: list[GateCheck] = []

        # Build integrity
        build_hash = self.compute_build_hash()
        report.build_hash = build_hash
        if self.expected_build_hash:
            match = bool(build_hash) and build_hash == self.expected_build_hash
            # --force-live must NOT bypass
            if self.force_live_flag and not match:
                match = False
            checks.append(
                GateCheck(
                    "build_hash",
                    match,
                    GateSeverity.CRITICAL,
                    "match" if match else "mismatch or missing (force-live ignored)",
                )
            )
        else:
            checks.append(
                GateCheck(
                    "build_hash",
                    True,
                    GateSeverity.WARNING,
                    "no expected hash configured (dev/CI)",
                )
            )

        def _probe(name: str, fn: IntegrityProbe | None, critical: bool = True) -> None:
            sev = GateSeverity.CRITICAL if critical else GateSeverity.WARNING
            if fn is None:
                checks.append(GateCheck(name, True, GateSeverity.WARNING, "probe not wired"))
                return
            try:
                ok = bool(fn())
            except Exception as exc:  # noqa: BLE001
                ok = False
                checks.append(GateCheck(name, False, sev, type(exc).__name__))
                return
            checks.append(GateCheck(name, ok, sev, "ok" if ok else "failed"))

        if self.connectivity is not None:
            try:
                ok = bool(self.connectivity())
            except Exception as exc:  # noqa: BLE001
                ok = False
                checks.append(
                    GateCheck("connectivity", False, GateSeverity.CRITICAL, type(exc).__name__)
                )
            else:
                checks.append(
                    GateCheck(
                        "connectivity", ok, GateSeverity.CRITICAL, "ok" if ok else "unreachable"
                    )
                )
        else:
            checks.append(GateCheck("connectivity", True, GateSeverity.WARNING, "probe not wired"))

        # Permissions
        trading = "UNKNOWN"
        withdrawal = self.withdrawal_status
        if self.permissions is not None:
            try:
                perms = self.permissions()
                trading = str(perms.get("trading", "UNKNOWN")).upper()
                withdrawal = str(perms.get("withdrawal", withdrawal)).upper()
            except Exception as exc:  # noqa: BLE001
                checks.append(
                    GateCheck("permissions", False, GateSeverity.CRITICAL, type(exc).__name__)
                )
                trading = "UNKNOWN"
        trading_ok = trading in ("ENABLED", "TRUE", "YES")
        checks.append(
            GateCheck(
                "trading_permission",
                trading_ok if self.permissions is not None else True,
                GateSeverity.CRITICAL if self.permissions is not None else GateSeverity.WARNING,
                trading,
            )
        )
        # Withdrawal must not be ENABLED for default canary safety
        # UNKNOWN is never considered safe for LIVE.
        wd_ok = withdrawal in ("DISABLED", "FALSE", "NO")
        checks.append(
            GateCheck(
                "withdrawal_disabled",
                wd_ok,
                GateSeverity.CRITICAL,
                withdrawal,
            )
        )

        # Time skew
        skew = self.time_skew_ms
        if skew is not None:
            skew_ok = abs(skew) <= self.max_time_skew_ms
            checks.append(
                GateCheck(
                    "time_sync",
                    skew_ok,
                    GateSeverity.CRITICAL,
                    f"skew_ms={skew}",
                )
            )
        else:
            checks.append(GateCheck("time_sync", True, GateSeverity.WARNING, "not measured"))

        _probe("database_integrity", self.db_integrity)
        _probe("model_registry", self.model_ok)
        _probe("recovery", self.recovery_ok)
        _probe("governor", self.governor_ok)
        _probe("risk_engine", self.risk_ok)
        _probe("control_plane", self.control_ok)

        checks.append(
            GateCheck(
                "micro_capital_active",
                limits.enabled,
                GateSeverity.CRITICAL,
                "enabled" if limits.enabled else "disabled",
            )
        )
        checks.append(
            GateCheck(
                "unresolved_unknown",
                not self.unresolved_unknown,
                GateSeverity.CRITICAL,
                "none" if not self.unresolved_unknown else "present",
            )
        )
        checks.append(
            GateCheck(
                "reconciliation",
                not self.reconciliation_mismatch,
                GateSeverity.CRITICAL,
                "ok" if not self.reconciliation_mismatch else "mismatch",
            )
        )

        # Live-only operational gates (not required for SOFTWARE GREEN)
        checks.append(
            GateCheck(
                "canary_round_trip",
                self.canary_round_trip_ok,
                GateSeverity.CRITICAL,
                "ok" if self.canary_round_trip_ok else "not completed",
            )
        )
        checks.append(
            GateCheck(
                "emergency_stop_test",
                self.emergency_stop_tested,
                GateSeverity.CRITICAL,
                "ok" if self.emergency_stop_tested else "not tested",
            )
        )

        # A LIVE decision requires real, wired probes. Missing probes may be
        # tolerated for SOFTWARE GREEN, but can never satisfy LIVE GO.
        if exchange_verified:
            required_live_probes = (
                ("connectivity", self.connectivity is not None),
                ("permissions", self.permissions is not None),
                ("time_sync", self.time_skew_ms is not None),
            )
            for name, wired in required_live_probes:
                if not wired:
                    checks.append(
                        GateCheck(
                            f"live_{name}_probe",
                            False,
                            GateSeverity.CRITICAL,
                            "probe not wired; LIVE blocked",
                        )
                    )

        report.checks = checks

        # Software green: critical checks that do not require real exchange canary
        software_critical = {
            "database_integrity",
            "model_registry",
            "recovery",
            "governor",
            "risk_engine",
            "control_plane",
            "micro_capital_active",
            "unresolved_unknown",
            "reconciliation",
            "withdrawal_disabled",
        }
        soft_fails = [
            c
            for c in checks
            if not c.passed and c.severity is GateSeverity.CRITICAL and c.name in software_critical
        ]
        # build_hash only critical when expected set
        for c in checks:
            if c.name == "build_hash" and not c.passed and c.severity is GateSeverity.CRITICAL:
                soft_fails.append(c)
        report.software_green = len(soft_fails) == 0

        # PRODUCTION LIVE GO requires software green + exchange-verified canary gates
        live_fails = [c for c in checks if not c.passed and c.severity is GateSeverity.CRITICAL]
        if not exchange_verified:
            report.live_decision = LiveDecision.NOT_VERIFIED
            report.production_live_verified = False
        elif live_fails:
            report.live_decision = LiveDecision.NO_GO
            report.production_live_verified = False
        else:
            report.live_decision = LiveDecision.GO
            report.production_live_verified = True

        return report

    def allow_live_submission(self, report: ProductionGateReport | None = None) -> bool:
        """Only True on explicit GO. Default PAPER path never calls this successfully in CI."""
        r = report or self.evaluate(exchange_verified=False)
        return r.live_decision is LiveDecision.GO

    def default_mode(self) -> ExecutionMode:
        return ExecutionMode.PAPER
