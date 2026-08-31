"""Phase 5E — N.U.N.G. paper risk evaluation. Fail-closed simulation gate."""

from __future__ import annotations

from typing import Any, Optional

from god.research.provenance import content_hash

from .models import build_paper_provenance
from .portfolio import PaperPortfolioState, PortfolioStatus
from .risk_models import (
    PaperRiskAssessment,
    RiskLevel,
    RiskStatus,
    SafetyDecision,
    SCHEMA_VERSION,
    make_risk_id,
)


class PaperRiskEngine:
    """
    Evaluate paper portfolio risk for simulation safety only.
    Never grants live trading authority.
    """

    def __init__(
        self,
        *,
        warning_drawdown: float = 0.10,
        critical_drawdown: float = 0.25,
        max_reason_codes: int = 20,
    ) -> None:
        self.warning_drawdown = warning_drawdown
        self.critical_drawdown = critical_drawdown
        self.max_reason_codes = max_reason_codes
        self._cache: dict[str, PaperRiskAssessment] = {}

    def evaluate(
        self,
        portfolio: Optional[PaperPortfolioState] = None,
        *,
        data_status: Optional[str] = None,
        decision_status: Optional[str] = None,
        decision_id: Optional[str] = None,
        cycle_id: Optional[str] = None,
        now_iso: Optional[str] = None,
        observation_timestamp: Optional[str] = None,
        max_drawdown: Optional[float] = None,
    ) -> PaperRiskAssessment:
        reasons: list[str] = []
        risk_status = RiskStatus.VALID
        risk_level = RiskLevel.NORMAL
        decision = SafetyDecision.PAPER_ALLOWED
        dd = max_drawdown

        # Fail-closed on data status
        ds = (data_status or "").upper()
        if ds in ("UNKNOWN", ""):
            if ds == "UNKNOWN":
                risk_status = RiskStatus.UNKNOWN
                reasons.append("data_unknown")
                decision = SafetyDecision.BLOCKED
                risk_level = RiskLevel.BLOCKED
        if ds == "STALE":
            risk_status = RiskStatus.STALE
            reasons.append("data_stale")
            decision = SafetyDecision.BLOCKED
            risk_level = RiskLevel.BLOCKED
        if ds in ("INVALID", "CORRUPTED", "MISSING", "UNAVAILABLE", "FAILED"):
            risk_status = (
                RiskStatus.CORRUPTED
                if ds == "CORRUPTED"
                else RiskStatus.INVALID
                if ds == "INVALID"
                else RiskStatus.MISSING_DATA
                if ds in ("MISSING", "UNAVAILABLE")
                else RiskStatus.FAILED
            )
            reasons.append(f"data_{ds.lower()}")
            decision = SafetyDecision.BLOCKED
            risk_level = RiskLevel.BLOCKED

        # Decision status interlock
        decs = (decision_status or "").upper()
        if decs in ("UNKNOWN", "BLOCKED", "INVALID", "STALE", "CORRUPTED"):
            reasons.append(f"decision_{decs.lower()}")
            decision = SafetyDecision.BLOCKED
            risk_level = RiskLevel.BLOCKED
            if decs == "CORRUPTED":
                risk_status = RiskStatus.CORRUPTED
            elif decs == "STALE":
                risk_status = RiskStatus.STALE
            elif decs == "UNKNOWN":
                risk_status = RiskStatus.UNKNOWN
            else:
                risk_status = RiskStatus.INVALID

        # Temporal
        if now_iso and observation_timestamp and observation_timestamp > now_iso:
            reasons.append("future_observation")
            decision = SafetyDecision.BLOCKED
            risk_level = RiskLevel.BLOCKED
            risk_status = RiskStatus.INVALID

        # Portfolio status
        if portfolio is not None:
            if portfolio.status == PortfolioStatus.CORRUPTED:
                reasons.append("portfolio_corrupted")
                decision = SafetyDecision.BLOCKED
                risk_level = RiskLevel.BLOCKED
                risk_status = RiskStatus.CORRUPTED
            if portfolio.status == PortfolioStatus.INVALID:
                reasons.append("portfolio_invalid")
                decision = SafetyDecision.BLOCKED
                risk_level = RiskLevel.BLOCKED
                risk_status = RiskStatus.INVALID
            if portfolio.holding is not None and portfolio.simulated_cash < 0:
                reasons.append("negative_cash")
                decision = SafetyDecision.BLOCKED
                risk_level = RiskLevel.BLOCKED

        # Drawdown (independent of portfolio object presence)
        if dd is not None:
            if dd >= self.critical_drawdown:
                reasons.append("critical_drawdown")
                decision = SafetyDecision.BLOCKED
                risk_level = RiskLevel.BLOCKED
            elif dd >= self.warning_drawdown:
                reasons.append("warning_drawdown")
                if risk_level == RiskLevel.NORMAL:
                    risk_level = RiskLevel.WARNING

        if portfolio is None and data_status is None and decision_status is None:
            risk_status = RiskStatus.MISSING_DATA
            reasons.append("missing_inputs")
            decision = SafetyDecision.BLOCKED
            risk_level = RiskLevel.BLOCKED

        reasons = reasons[: self.max_reason_codes]
        payload = {
            "decision": decision.value,
            "risk_level": risk_level.value,
            "risk_status": risk_status.value,
            "reasons": reasons,
            "dd": dd,
            "decision_id": decision_id or "",
            "cycle_id": cycle_id or "",
            "schema": SCHEMA_VERSION,
        }
        rid = make_risk_id(payload)
        if rid in self._cache:
            return self._cache[rid]
        assessment = PaperRiskAssessment(
            risk_id=rid,
            decision=decision,
            risk_level=risk_level,
            risk_status=risk_status,
            content_hash=content_hash(payload),
            reason_codes=tuple(reasons),
            drawdown=dd,
            decision_id=decision_id,
            cycle_id=cycle_id,
            provenance=build_paper_provenance(payload),
        )
        self._cache[rid] = assessment
        return assessment
