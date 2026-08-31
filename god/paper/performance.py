"""Phase 5D — N.U.N.G. paper performance metrics. Simulation only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from god.research.provenance import content_hash

from .portfolio import PaperPortfolioEngine, PaperPortfolioState, PortfolioStatus
from .models import build_paper_provenance


class MetricsStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID = "INVALID"
    CORRUPTED = "CORRUPTED"


@dataclass(frozen=True)
class PerformanceMetrics:
    metrics_id: str
    status: MetricsStatus
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    starting_equity: float
    current_equity: float
    return_pct: Optional[float]
    max_drawdown: Optional[float]
    completed_cycles: int
    content_hash: str
    provenance: Optional[dict[str, Any]] = None
    notes: str = "paper_performance_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics_id": self.metrics_id,
            "status": self.status.value,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "starting_equity": self.starting_equity,
            "current_equity": self.current_equity,
            "return_pct": self.return_pct,
            "max_drawdown": self.max_drawdown,
            "completed_cycles": self.completed_cycles,
            "content_hash": self.content_hash,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


class PaperPerformanceEngine:
    def __init__(self, portfolio: PaperPortfolioEngine) -> None:
        self.portfolio = portfolio

    def compute(self) -> PerformanceMetrics:
        st = self.portfolio.state
        hist = self.portfolio.history()
        starting = self.portfolio.initial_cash
        current = st.simulated_equity
        realized = st.realized_pnl
        unrealized = st.unrealized_pnl
        total = realized + unrealized

        if st.status == PortfolioStatus.CORRUPTED:
            status = MetricsStatus.CORRUPTED
            ret = None
            dd = None
        elif not hist and st.status == PortfolioStatus.EMPTY:
            status = MetricsStatus.INSUFFICIENT_DATA
            ret = None
            dd = None
        else:
            status = MetricsStatus.VALID
            ret = ((current - starting) / starting * 100.0) if starting else None
            dd = self._max_drawdown(hist, starting)

        completed = sum(
            1 for h in hist if h.status == PortfolioStatus.CLOSED_PAPER
        )
        payload = {
            "realized": realized,
            "unrealized": unrealized,
            "total": total,
            "equity": current,
            "status": status.value,
        }
        mid = "pm-" + content_hash(payload)[:20]
        return PerformanceMetrics(
            metrics_id=mid,
            status=status,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            total_pnl=total,
            starting_equity=starting,
            current_equity=current,
            return_pct=ret,
            max_drawdown=dd,
            completed_cycles=completed,
            content_hash=content_hash(payload),
            provenance=build_paper_provenance(payload),
        )

    def _max_drawdown(
        self, hist: list[PaperPortfolioState], starting: float
    ) -> Optional[float]:
        if not hist:
            return None
        peak = starting
        max_dd = 0.0
        for h in hist:
            eq = h.simulated_equity
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
        return max_dd
