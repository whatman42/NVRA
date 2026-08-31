"""CapitalSafetyEngine — system safety posture only. No allocation / sizing."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now
from god.research.provenance import build_provenance

from .models import (
    CapitalState,
    CapitalStateRecord,
    CapitalTransitionRecord,
    make_transition_id,
)
from .registry import CapitalRegistry
from .states import assert_transition, can_transition


class CapitalSafetyEngine:
    def __init__(self, registry: Optional[CapitalRegistry] = None) -> None:
        self.registry = registry or CapitalRegistry()
        if self.registry.get_record() is None:
            self._init_record(CapitalState.INITIALIZING)

    def _init_record(self, state: CapitalState) -> CapitalStateRecord:
        prov = build_provenance(
            origin="capital_safety",
            payload={"state": state.value, "init": True},
        )
        rec = CapitalStateRecord(
            record_id=str(uuid4()),
            state=state,
            updated_at=utc_now(),
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
        )
        self.registry.set_record(rec)
        return rec

    @property
    def state(self) -> CapitalState:
        rec = self.registry.get_record()
        return rec.state if rec else CapitalState.UNKNOWN

    def transition(
        self,
        to_state: CapitalState,
        *,
        reason: str,
        evidence_refs: Optional[list[str]] = None,
        actor: str = "capital_safety",
        metadata: Optional[dict[str, Any]] = None,
    ) -> CapitalStateRecord:
        if not reason or not reason.strip():
            raise ValueError("transition requires non-empty reason")

        rec = self.registry.get_record()
        if rec is None:
            rec = self._init_record(CapitalState.UNKNOWN)

        before = rec.state
        if before == to_state:
            return rec  # idempotent no-op

        assert_transition(before, to_state)

        ev_key = "|".join(sorted(evidence_refs or []))
        tid = make_transition_id(before, to_state, reason.strip(), ev_key)
        existing = self.registry.get_transition(tid)
        if existing is not None:
            # already applied logically
            return rec

        prov = build_provenance(
            origin="capital_transition",
            payload={
                "transition_id": tid,
                "before": before.value,
                "after": to_state.value,
                "reason": reason.strip(),
            },
        )
        tr = CapitalTransitionRecord(
            transition_id=tid,
            state_before=before,
            state_after=to_state,
            reason=reason.strip(),
            evidence_refs=tuple(evidence_refs or ()),
            timestamp=utc_now(),
            actor=actor,
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            metadata=dict(metadata or {}),
        )
        self.registry.add_transition(tr)

        rec.state = to_state
        rec.updated_at = tr.timestamp
        rec.last_transition_id = tid
        rec.transition_ids = list(rec.transition_ids) + [tid]
        rec.evidence_refs = list(
            dict.fromkeys(list(rec.evidence_refs) + list(evidence_refs or []))
        )
        self.registry.set_record(rec)
        return rec

    def apply_permission_hint(
        self,
        permission_value: str,
        *,
        evidence_refs: Optional[list[str]] = None,
        reason: Optional[str] = None,
    ) -> CapitalStateRecord:
        """
        Map PolicyDecision.permission → suggested capital state transition.
        This does NOT execute trades. Caller still owns execution.
        Fail-closed mapping.
        """
        perm = (permission_value or "UNKNOWN").upper()
        current = self.state
        mapping = {
            "BLOCK": CapitalState.EMERGENCY_STOP
            if current != CapitalState.EMERGENCY_STOP
            else CapitalState.EMERGENCY_STOP,
            "PAUSE": CapitalState.PAUSED,
            "RESTRICT": CapitalState.RESTRICTED,
            "UNKNOWN": CapitalState.UNKNOWN,
            "ALLOW": CapitalState.NORMAL,
        }
        target = mapping.get(perm, CapitalState.UNKNOWN)

        # ALLOW must not force NORMAL from EMERGENCY_STOP without recovery path
        if perm == "ALLOW" and current == CapitalState.EMERGENCY_STOP:
            target = CapitalState.RECOVERY
        if perm == "ALLOW" and current == CapitalState.PAUSED:
            target = CapitalState.RECOVERY

        if not can_transition(current, target):
            # fail-closed: go UNKNOWN if cannot apply
            if can_transition(current, CapitalState.UNKNOWN):
                target = CapitalState.UNKNOWN
            else:
                return self.registry.get_record()  # type: ignore

        return self.transition(
            target,
            reason=reason or f"policy_permission={perm}",
            evidence_refs=evidence_refs,
            actor="policy_hint",
        )

    def is_allowed_transition(self, to_state: CapitalState) -> bool:
        return can_transition(self.state, to_state)
