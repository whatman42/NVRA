"""Append-only CognitiveDecisionLedger for N.U.N.G. — no trading orders."""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import (
    ControlConfig,
    DecisionStatus,
    LedgerRecord,
    LedgerStage,
    build_control_provenance,
    make_record_id,
)


class CognitiveDecisionLedger:
    def __init__(self, config: Optional[ControlConfig] = None) -> None:
        self.config = config or ControlConfig()
        self._records: list[LedgerRecord] = []
        self._by_id: dict[str, LedgerRecord] = {}

    def append(
        self,
        *,
        cycle_id: str,
        correlation_id: str,
        stage: LedgerStage,
        status: DecisionStatus,
        snapshot_id: Optional[str] = None,
        discovery_result_id: Optional[str] = None,
        selection_id: Optional[str] = None,
        attention_id: Optional[str] = None,
        strategy_ref: Optional[str] = None,
        symbol: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        policy_ref: Optional[str] = None,
        drift_ref: Optional[str] = None,
        regime_ref: Optional[str] = None,
        reality_gap_ref: Optional[str] = None,
        reason_code: Optional[str] = None,
        truncated: bool = False,
        notes: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> LedgerRecord:
        payload = {
            "cycle_id": cycle_id,
            "correlation_id": correlation_id,
            "stage": stage.value,
            "status": status.value,
            "snapshot_id": snapshot_id,
            "discovery_result_id": discovery_result_id,
            "selection_id": selection_id,
            "attention_id": attention_id,
            "strategy_ref": strategy_ref,
            "symbol": symbol,
            "opportunity_id": opportunity_id,
            "policy_ref": policy_ref,
            "drift_ref": drift_ref,
            "regime_ref": regime_ref,
            "reality_gap_ref": reality_gap_ref,
            "reason_code": reason_code,
            "truncated": truncated,
            "schema_version": self.config.schema_version,
        }
        rid = make_record_id(payload)
        if rid in self._by_id:
            existing = self._by_id[rid]
            # mark returned existing without mutating identity
            existing.returned_existing = True
            return existing

        ch = content_hash(payload)
        rec = LedgerRecord(
            record_id=rid,
            cycle_id=cycle_id,
            correlation_id=correlation_id,
            stage=stage,
            status=status,
            timestamp=utc_now(),
            content_hash=ch,
            schema_version=self.config.schema_version,
            snapshot_id=snapshot_id,
            discovery_result_id=discovery_result_id,
            selection_id=selection_id,
            attention_id=attention_id,
            strategy_ref=strategy_ref,
            symbol=symbol,
            opportunity_id=opportunity_id,
            policy_ref=policy_ref,
            drift_ref=drift_ref,
            regime_ref=regime_ref,
            reality_gap_ref=reality_gap_ref,
            reason_code=reason_code,
            provenance=build_control_provenance(payload),
            truncated=truncated,
            notes=notes,
            metadata=dict(metadata or {}),
        )
        self._by_id[rid] = rec
        self._records.append(rec)
        while len(self._records) > self.config.max_ledger_records:
            old = self._records.pop(0)
            self._by_id.pop(old.record_id, None)
        return rec

    def for_cycle(self, cycle_id: str) -> list[LedgerRecord]:
        return [r for r in self._records if r.cycle_id == cycle_id]

    def for_correlation(self, correlation_id: str) -> list[LedgerRecord]:
        return [r for r in self._records if r.correlation_id == correlation_id]

    def recent(self, n: int = 50) -> list[LedgerRecord]:
        return self._records[-n:]

    def get(self, record_id: str) -> Optional[LedgerRecord]:
        return self._by_id.get(record_id)
