"""Audit service for N.U.N.G. cognitive cycles — deterministic, provenance-preserving."""

from __future__ import annotations

from typing import Any, Optional

from .ledger import CognitiveDecisionLedger
from .models import ControlConfig, LedgerRecord


class CognitiveAuditService:
    def __init__(
        self,
        ledger: CognitiveDecisionLedger,
        config: Optional[ControlConfig] = None,
    ) -> None:
        self.ledger = ledger
        self.config = config or ControlConfig()
        self._audit_log: list[dict[str, Any]] = []

    def audit_cycle(self, cycle_id: str) -> dict[str, Any]:
        records = self.ledger.for_cycle(cycle_id)
        if not records:
            out = {
                "cycle_id": cycle_id,
                "found": False,
                "records": [],
                "summary": "no_ledger_records",
            }
        else:
            out = {
                "cycle_id": cycle_id,
                "found": True,
                "correlation_ids": sorted({r.correlation_id for r in records}),
                "stages": [r.stage.value for r in records],
                "statuses": [r.status.value for r in records],
                "snapshot_ids": sorted({r.snapshot_id for r in records if r.snapshot_id}),
                "discovery_ids": sorted(
                    {r.discovery_result_id for r in records if r.discovery_result_id}
                ),
                "selection_ids": sorted(
                    {r.selection_id for r in records if r.selection_id}
                ),
                "truncated": any(r.truncated for r in records),
                "returned_existing": any(r.returned_existing for r in records),
                "reason_codes": [r.reason_code for r in records if r.reason_code],
                "records": [r.to_dict() for r in records],
                "summary": f"records={len(records)}",
            }
        self._push(out)
        return out

    def audit_correlation(self, correlation_id: str) -> dict[str, Any]:
        records = self.ledger.for_correlation(correlation_id)
        out = {
            "correlation_id": correlation_id,
            "found": bool(records),
            "cycle_ids": sorted({r.cycle_id for r in records}),
            "records": [r.to_dict() for r in records],
        }
        self._push(out)
        return out

    def _push(self, entry: dict[str, Any]) -> None:
        self._audit_log.append(entry)
        while len(self._audit_log) > self.config.max_audit_records:
            self._audit_log.pop(0)

    def recent_audits(self, n: int = 20) -> list[dict[str, Any]]:
        return self._audit_log[-n:]
