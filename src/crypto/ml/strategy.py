"""Bridge: Prediction → TradeProposal. Never creates exchange orders."""

from __future__ import annotations

from crypto.ml.prediction import Direction, Prediction
from crypto.risk.models import Side, TradeProposal


def prediction_to_proposal(
    prediction: Prediction,
    *,
    exchange_id: str,
    account_id: str = "default",
    quantity: float = 0.0,
    price: float | None = None,
    stop_price: float | None = None,
    strategy_id: str = "ml_v1",
    min_confidence: float = 0.55,
) -> TradeProposal | None:
    """Convert an actionable prediction into a risk-evaluated trade proposal.

    Returns None if not actionable. Caller must still pass through RiskEngine.
    """
    if not prediction.is_actionable(min_confidence=min_confidence):
        return None
    if prediction.direction is Direction.UP:
        side = Side.BUY
    elif prediction.direction is Direction.DOWN:
        side = Side.SELL
    else:
        return None
    return TradeProposal(
        exchange_id=exchange_id,
        account_id=account_id,
        symbol=prediction.symbol,
        side=side,
        requested_quantity=quantity,
        requested_price=price,
        stop_price=stop_price,
        strategy_id=strategy_id,
        timestamp_ms=prediction.generated_at_ms,
    )
