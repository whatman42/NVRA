"""EnsemblePrediction / Opportunity → TradeProposal. Never executes."""

from __future__ import annotations

from crypto.ensemble.aggregate import EnsemblePrediction
from crypto.ml.strategy import prediction_to_proposal
from crypto.risk.models import TradeProposal
from crypto.scanner.opportunity import Feasibility, Opportunity


def opportunity_to_proposal(
    opp: Opportunity,
    *,
    quantity: float = 0.0,
    price: float | None = None,
    strategy_id: str = "scanner_v1",
    min_confidence: float = 0.55,
) -> TradeProposal | None:
    """Build a TradeProposal for RiskEngine. Returns None if not actionable."""
    if opp.feasibility is Feasibility.ORDER_NOT_FEASIBLE:
        return None
    if opp.ensemble is None:
        return None
    pred = opp.ensemble.to_prediction()
    return prediction_to_proposal(
        pred,
        exchange_id=opp.exchange_id,
        account_id=opp.account_id,
        quantity=quantity,
        price=price if price is not None else opp.mid_price,
        strategy_id=strategy_id,
        min_confidence=min_confidence,
    )


def ensemble_to_proposal(
    ep: EnsemblePrediction,
    *,
    exchange_id: str,
    account_id: str = "default",
    quantity: float = 0.0,
    price: float | None = None,
    strategy_id: str = "ensemble_v1",
    min_confidence: float = 0.55,
) -> TradeProposal | None:
    return prediction_to_proposal(
        ep.to_prediction(),
        exchange_id=exchange_id,
        account_id=account_id,
        quantity=quantity,
        price=price,
        strategy_id=strategy_id,
        min_confidence=min_confidence,
    )
