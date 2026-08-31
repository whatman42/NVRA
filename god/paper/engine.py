"""PaperExecutionEngine — N.U.N.G. Phase 5B. Simulation only."""

from __future__ import annotations

from typing import Any, Optional

from god.execution_contract import (
    ExecutionIntent,
    IntentStatus,
    ExecutionValidator,
)
from god.memory.database import utc_now
from god.research.provenance import content_hash

from .fill import simulate_fill
from .models import (
    PaperExecution,
    PaperStatus,
    SCHEMA_VERSION,
    build_paper_provenance,
    make_paper_id,
)
from .state import PaperState


class PaperExecutionEngine:
    """
    ExecutionIntent (VALID) + optional market observation → PaperExecution.
    Never contacts a broker. Never allocates capital.
    """

    def __init__(
        self,
        *,
        validator: Optional[ExecutionValidator] = None,
        state: Optional[PaperState] = None,
    ) -> None:
        self.validator = validator or ExecutionValidator()
        self.state = state or PaperState()

    def simulate(
        self,
        intent: ExecutionIntent,
        *,
        market_observation: Optional[dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
        now_iso: Optional[str] = None,
    ) -> PaperExecution:
        now = now_iso or utc_now()

        # identity payload for idempotency
        key_payload = {
            "intent_id": intent.intent_id,
            "snapshot_id": snapshot_id or "",
            "schema_version": SCHEMA_VERSION,
            "symbol": intent.symbol,
            "action": intent.intent_action.value,
        }
        # include last obs value in identity when present for changed-market new id
        if market_observation:
            obs = market_observation.get(intent.symbol) or market_observation.get(
                intent.symbol.upper()
            )
            if isinstance(obs, dict) and obs.get("values"):
                key_payload["last_value"] = obs["values"][-1]
        pid = make_paper_id(key_payload)
        existing = self.state.get(pid)
        if existing is not None:
            return existing

        ok, status, reason = self.validator.validate(intent, now_iso=now)
        if not ok or intent.intent_status not in (IntentStatus.VALID, status) and status != IntentStatus.VALID:
            # if validator failed
            if not ok:
                return self._reject(
                    pid, intent, now, (reason,), PaperStatus.PAPER_REJECTED
                )
        if status != IntentStatus.VALID:
            return self._reject(
                pid, intent, now, (status.value, reason), PaperStatus.PAPER_REJECTED
            )

        fill, fill_reason = simulate_fill(
            paper_execution_id=pid,
            symbol=intent.symbol,
            market_observation=market_observation,
            simulated_at=now,
            snapshot_id=snapshot_id,
            now_iso=now,
        )
        if fill is None:
            return self._reject(
                pid, intent, now, (fill_reason,), PaperStatus.PAPER_REJECTED
            )

        payload = {
            "paper_execution_id": pid,
            "intent_id": intent.intent_id,
            "decision_id": intent.decision_id,
            "status": PaperStatus.PAPER_SIMULATED.value,
            "fill_id": fill.fill_id,
        }
        execution = PaperExecution(
            paper_execution_id=pid,
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            cycle_id=intent.cycle_id,
            symbol=intent.symbol,
            action=intent.intent_action.value,
            status=PaperStatus.PAPER_SIMULATED,
            simulated_at=now,
            content_hash=content_hash(payload),
            fill=fill,
            provenance=build_paper_provenance(payload),
            reason_codes=("paper_simulated",),
            notes="PAPER_SIMULATION_ONLY — not live execution",
        )
        return self.state.put(execution)

    def _reject(
        self,
        pid: str,
        intent: ExecutionIntent,
        now: str,
        reasons: tuple[str, ...],
        status: PaperStatus,
    ) -> PaperExecution:
        existing = self.state.get(pid)
        if existing is not None:
            return existing
        payload = {
            "paper_execution_id": pid,
            "intent_id": intent.intent_id,
            "status": status.value,
            "reasons": list(reasons),
        }
        execution = PaperExecution(
            paper_execution_id=pid,
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            cycle_id=intent.cycle_id,
            symbol=intent.symbol,
            action=intent.intent_action.value,
            status=status,
            simulated_at=now,
            content_hash=content_hash(payload),
            provenance=build_paper_provenance(payload),
            reason_codes=reasons,
            notes="paper_rejected",
        )
        return self.state.put(execution)
