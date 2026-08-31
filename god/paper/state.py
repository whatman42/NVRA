"""Bounded paper state store for N.U.N.G. — not real positions."""

from __future__ import annotations

from typing import Optional

from .models import PaperExecution, PaperStatus


class PaperState:
    """Isolated simulation history. Never represents broker positions."""

    def __init__(self, max_records: int = 500) -> None:
        self.max_records = max_records
        self._by_id: dict[str, PaperExecution] = {}
        self._order: list[str] = []

    def put(self, execution: PaperExecution) -> PaperExecution:
        if execution.paper_execution_id in self._by_id:
            return self._by_id[execution.paper_execution_id]
        self._by_id[execution.paper_execution_id] = execution
        self._order.append(execution.paper_execution_id)
        while len(self._order) > self.max_records:
            old = self._order.pop(0)
            self._by_id.pop(old, None)
        return execution

    def get(self, paper_execution_id: str) -> Optional[PaperExecution]:
        return self._by_id.get(paper_execution_id)

    def recent(self, n: int = 50) -> list[PaperExecution]:
        ids = self._order[-n:]
        return [self._by_id[i] for i in ids if i in self._by_id]

    def count_simulated(self) -> int:
        return sum(
            1
            for e in self._by_id.values()
            if e.status == PaperStatus.PAPER_SIMULATED
        )
