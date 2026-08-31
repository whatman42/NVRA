"""Phase 5H — N.U.N.G. paper production readiness gate. Pre-live only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from god.research.provenance import content_hash

from .models import build_paper_provenance
from .orchestrator import PaperOrchestrator, PaperPipelineResult, PipelineStatus


class ReadinessStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"


SCHEMA_VERSION = "paper-readiness-5h-v1"


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ReadinessReport:
    readiness_id: str
    status: ReadinessStatus
    checks: tuple[ReadinessCheck, ...]
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    pipeline_result_id: Optional[str] = None
    decision_id: Optional[str] = None
    cycle_id: Optional[str] = None
    reason_codes: tuple[str, ...] = ()
    provenance: Optional[dict[str, Any]] = None
    notes: str = "paper_readiness_pre_live_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness_id": self.readiness_id,
            "status": self.status.value,
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks],
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "pipeline_result_id": self.pipeline_result_id,
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "reason_codes": list(self.reason_codes),
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


class PaperReadinessGate:
    """
    Final pre-live paper readiness evaluation.
    READY only when all mandatory paper pipeline stages succeed.
    UNKNOWN/STALE/INVALID/CORRUPTED/BLOCKED → NOT_READY.
    """

    def __init__(self, orchestrator: Optional[PaperOrchestrator] = None) -> None:
        self.orchestrator = orchestrator or PaperOrchestrator()
        self._cache: dict[str, ReadinessReport] = {}

    def evaluate(
        self,
        decision: Any = None,
        *,
        pipeline_result: Optional[PaperPipelineResult] = None,
        market_observation: Optional[dict[str, Any]] = None,
        data_status: str = "HEALTHY",
        now_iso: Optional[str] = None,
        max_drawdown: Optional[float] = None,
    ) -> ReadinessReport:
        checks: list[ReadinessCheck] = []
        reasons: list[str] = []

        if pipeline_result is None:
            if decision is None:
                checks.append(ReadinessCheck("decision", False, "missing"))
                reasons.append("missing_decision")
                return self._report(checks, reasons, None)
            pipeline_result = self.orchestrator.run_paper_cycle(
                decision,
                market_observation=market_observation,
                data_status=data_status,
                now_iso=now_iso,
                max_drawdown=max_drawdown,
            )

        # Pipeline status
        ok_pipe = pipeline_result.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.RETURN_EXISTING,
        )
        checks.append(
            ReadinessCheck(
                "pipeline",
                ok_pipe,
                pipeline_result.status.value,
            )
        )
        if not ok_pipe:
            reasons.append(f"pipeline_{pipeline_result.status.value.lower()}")

        # Lifecycle
        life_ok = pipeline_result.lifecycle_state == "COMPLETED"
        checks.append(
            ReadinessCheck(
                "lifecycle",
                life_ok,
                pipeline_result.lifecycle_state or "missing",
            )
        )
        if not life_ok:
            reasons.append("lifecycle_incomplete")

        # Identifiers
        for name, val in (
            ("decision_id", pipeline_result.decision_id),
            ("cycle_id", pipeline_result.cycle_id),
            ("intent_id", pipeline_result.intent_id),
        ):
            present = bool(val)
            checks.append(ReadinessCheck(name, present, str(val or "")))
            if not present:
                reasons.append(f"missing_{name}")

        # Provenance
        prov_ok = bool(pipeline_result.provenance) and bool(pipeline_result.content_hash)
        checks.append(ReadinessCheck("provenance", prov_ok, ""))
        if not prov_ok:
            reasons.append("missing_provenance")

        # Data status fail-closed
        ds = (data_status or "").upper()
        data_ok = ds not in (
            "UNKNOWN",
            "STALE",
            "INVALID",
            "CORRUPTED",
            "BLOCKED",
            "MISSING",
            "UNAVAILABLE",
            "FAILED",
        )
        checks.append(ReadinessCheck("data_status", data_ok, ds or "empty"))
        if not data_ok:
            reasons.append(f"data_{ds.lower() or 'empty'}")

        # No live fields
        d = pipeline_result.to_dict()
        live_free = "order_id" not in d and "position_id" not in d
        checks.append(ReadinessCheck("no_live_fields", live_free, ""))
        if not live_free:
            reasons.append("live_fields_present")

        status = (
            ReadinessStatus.READY
            if all(c.passed for c in checks)
            else ReadinessStatus.NOT_READY
        )
        return self._report(
            checks,
            reasons,
            pipeline_result,
            status=status,
        )

    def _report(
        self,
        checks: list[ReadinessCheck],
        reasons: list[str],
        pipeline_result: Optional[PaperPipelineResult],
        *,
        status: Optional[ReadinessStatus] = None,
    ) -> ReadinessReport:
        if status is None:
            status = (
                ReadinessStatus.READY
                if all(c.passed for c in checks)
                else ReadinessStatus.NOT_READY
            )
        payload = {
            "status": status.value,
            "checks": [c.name + ":" + str(c.passed) for c in checks],
            "reasons": reasons,
            "pipe": pipeline_result.result_id if pipeline_result else "",
            "schema": SCHEMA_VERSION,
        }
        rid = "ready-" + content_hash(payload)[:24]
        if rid in self._cache:
            return self._cache[rid]
        report = ReadinessReport(
            readiness_id=rid,
            status=status,
            checks=tuple(checks),
            content_hash=content_hash(payload),
            pipeline_result_id=pipeline_result.result_id if pipeline_result else None,
            decision_id=pipeline_result.decision_id if pipeline_result else None,
            cycle_id=pipeline_result.cycle_id if pipeline_result else None,
            reason_codes=tuple(reasons),
            provenance=build_paper_provenance(payload),
        )
        self._cache[rid] = report
        return report
