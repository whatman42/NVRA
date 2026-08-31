"""Phase 5E — N.U.N.G. paper safety gate facade."""

from __future__ import annotations

from typing import Optional

from .portfolio import PaperPortfolioState
from .risk import PaperRiskEngine
from .risk_models import PaperRiskAssessment, SafetyDecision


class PaperSafetyGate:
    """Fail-closed gate between cognitive/paper pipeline and portfolio progression."""

    def __init__(self, risk_engine: Optional[PaperRiskEngine] = None) -> None:
        self.risk = risk_engine or PaperRiskEngine()

    def allow_paper_progression(
        self,
        *,
        portfolio: Optional[PaperPortfolioState] = None,
        data_status: Optional[str] = None,
        decision_status: Optional[str] = None,
        decision_id: Optional[str] = None,
        cycle_id: Optional[str] = None,
        now_iso: Optional[str] = None,
        observation_timestamp: Optional[str] = None,
        max_drawdown: Optional[float] = None,
    ) -> tuple[bool, PaperRiskAssessment]:
        assessment = self.risk.evaluate(
            portfolio,
            data_status=data_status,
            decision_status=decision_status,
            decision_id=decision_id,
            cycle_id=cycle_id,
            now_iso=now_iso,
            observation_timestamp=observation_timestamp,
            max_drawdown=max_drawdown,
        )
        allowed = assessment.decision == SafetyDecision.PAPER_ALLOWED
        return allowed, assessment
