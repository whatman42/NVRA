"""Reassessment adapter for N.U.N.G. — calls CognitiveLoopEngine.reassess without modifying loop."""

from __future__ import annotations

from typing import Any, Optional

from god.loop import CognitiveLoopEngine, CycleResult
from god.research.provenance import content_hash

from .models import DecisionConfig


class ReassessmentService:
    """
    Invokes canonical CognitiveLoopEngine.reassess(previous).
    Tracks triggers with idempotent fingerprints.
    """

    def __init__(self, config: Optional[DecisionConfig] = None) -> None:
        self.config = config or DecisionConfig()
        self._triggers: dict[str, str] = {}  # fingerprint → cycle_id
        self._trigger_order: list[str] = []

    def trigger_fingerprint(
        self,
        *,
        cycle_id: str,
        evidence_fp: str,
        reason: str,
    ) -> str:
        return content_hash({"c": cycle_id, "e": evidence_fp, "r": reason})

    def should_run(self, fingerprint: str) -> bool:
        if fingerprint in self._triggers:
            return False  # RETURN_EXISTING
        return True

    def mark(self, fingerprint: str, cycle_id: str) -> None:
        if fingerprint in self._triggers:
            return
        self._triggers[fingerprint] = cycle_id
        self._trigger_order.append(fingerprint)
        while len(self._trigger_order) > self.config.max_triggers:
            old = self._trigger_order.pop(0)
            self._triggers.pop(old, None)

    def reassess(
        self,
        engine: CognitiveLoopEngine,
        previous: CycleResult,
        *,
        reason: str = "FORCE_REASSESS",
        evidence_fp: str = "",
    ) -> tuple[CycleResult, bool]:
        """
        Returns (result, is_new).
        is_new=False means duplicate trigger RETURN_EXISTING (caller should not treat as fresh).
        """
        fp = self.trigger_fingerprint(
            cycle_id=previous.cycle_id,
            evidence_fp=evidence_fp or previous.cycle_id,
            reason=reason,
        )
        if not self.should_run(fp):
            return previous, False
        result = engine.reassess(previous)
        self.mark(fp, result.cycle_id)
        return result, True
