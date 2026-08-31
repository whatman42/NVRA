"""Market quote contract + validation. NO_NEW_ENTRY on invalid/stale."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Quote:
    symbol: str
    timestamp: float  # unix seconds
    bid: float
    ask: float
    last: Optional[float] = None
    bid_qty: Optional[float] = None
    ask_qty: Optional[float] = None
    volume: Optional[float] = None
    source: str = "unknown"
    sequence: Optional[int] = None


@dataclass(frozen=True)
class QuoteValidation:
    ok: bool
    reasons: tuple[str, ...] = ()
    spread: Optional[float] = None
    spread_pct: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "spread": self.spread,
            "spread_pct": self.spread_pct,
        }


def validate_quote(
    q: Quote,
    *,
    now: Optional[float] = None,
    max_age_seconds: float = 30.0,
    max_spread_pct: float = 0.01,
    min_qty: float = 0.0,
    last_sequence: Optional[int] = None,
) -> QuoteValidation:
    reasons: list[str] = []
    if not q.symbol:
        reasons.append("missing_symbol")
    if q.bid is None or q.ask is None:
        reasons.append("missing_bid_ask")
    else:
        if q.bid <= 0 or q.ask <= 0:
            reasons.append("price_le_zero")
        if q.ask < q.bid:
            reasons.append("crossed_book")
    if q.bid_qty is not None and q.bid_qty < 0:
        reasons.append("qty_negative")
    if q.ask_qty is not None and q.ask_qty < 0:
        reasons.append("qty_negative")
    if q.volume is not None and q.volume < 0:
        reasons.append("volume_negative")
    if q.timestamp is None or q.timestamp <= 0:
        reasons.append("invalid_timestamp")
    import time

    now = now if now is not None else time.time()
    if q.timestamp > 0 and (now - q.timestamp) > max_age_seconds:
        reasons.append("stale_data")
    spread = None
    spread_pct = None
    if q.bid and q.ask and q.bid > 0:
        spread = q.ask - q.bid
        mid = (q.ask + q.bid) / 2.0
        spread_pct = spread / mid if mid else None
        if spread_pct is not None and spread_pct > max_spread_pct:
            reasons.append("spread_too_wide")
    if min_qty > 0:
        bq = q.bid_qty if q.bid_qty is not None else 0.0
        aq = q.ask_qty if q.ask_qty is not None else 0.0
        if bq < min_qty and aq < min_qty:
            reasons.append("insufficient_liquidity")
    if last_sequence is not None and q.sequence is not None:
        if q.sequence < last_sequence:
            reasons.append("out_of_order_sequence")
        elif q.sequence == last_sequence:
            reasons.append("duplicate_sequence")
        elif q.sequence > last_sequence + 1:
            reasons.append("sequence_gap")
    return QuoteValidation(ok=len(reasons) == 0, reasons=tuple(reasons), spread=spread, spread_pct=spread_pct)
