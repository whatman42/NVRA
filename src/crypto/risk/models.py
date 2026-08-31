"""Trade proposals, risk decisions, and safety state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from crypto.portfolio.models import AccountKey


class Side(Enum):
    BUY = auto()
    SELL = auto()


class RiskVerdict(Enum):
    APPROVED = auto()
    REJECTED = auto()
    BLOCKED = auto()


class SafetyMode(Enum):
    """Central kill-switch / circuit-breaker state."""

    NORMAL = auto()
    WARNING = auto()
    BLOCK_NEW_ENTRIES = auto()
    REDUCE_ONLY = auto()
    EMERGENCY_STOP = auto()


class RejectReason(Enum):
    """Machine-readable rejection / block reasons."""

    NONE = auto()
    KILL_SWITCH = auto()
    SAFETY_MODE = auto()
    STALE_MARKET_DATA = auto()
    INVALID_MARKET_DATA = auto()
    UNKNOWN_MARKET_DATA = auto()
    INSUFFICIENT_BALANCE = auto()
    ORDER_BELOW_MINIMUM = auto()
    MAX_POSITION_SIZE = auto()
    MAX_SYMBOL_EXPOSURE = auto()
    MAX_EXCHANGE_EXPOSURE = auto()
    MAX_PORTFOLIO_EXPOSURE = auto()
    MAX_CONCURRENT_POSITIONS = auto()
    DAILY_LOSS_LIMIT = auto()
    DRAWDOWN_LIMIT = auto()
    CONSECUTIVE_LOSSES = auto()
    RECONCILIATION_MISMATCH = auto()
    EXCHANGE_UNAVAILABLE = auto()
    INVALID_PROPOSAL = auto()
    ZERO_SIZE = auto()


@dataclass(frozen=True, slots=True)
class TradeProposal:
    """Hypothetical trade for RiskEngine evaluation. Never submitted in Phase 4."""

    exchange_id: str
    account_id: str
    symbol: str
    side: Side
    requested_quantity: float
    requested_price: float | None
    stop_price: float | None = None
    strategy_id: str = ""
    timestamp_ms: int | None = None

    @property
    def account(self) -> AccountKey:
        return AccountKey(self.exchange_id, self.account_id)


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Authoritative risk outcome for a TradeProposal."""

    verdict: RiskVerdict
    reason: RejectReason
    message: str
    risk_score: float  # 0.0 (safe) .. 1.0 (max risk) or higher when blocked
    allowed_quantity: float
    allowed_notional: float
    current_exposure: float
    projected_exposure: float
    proposal: TradeProposal | None = None

    @property
    def approved(self) -> bool:
        return self.verdict is RiskVerdict.APPROVED

    @property
    def executable(self) -> bool:
        """True only when approved with positive allowed size."""
        return (
            self.verdict is RiskVerdict.APPROVED
            and self.allowed_quantity > 0
            and self.allowed_notional > 0
        )


@dataclass(frozen=True, slots=True)
class MarketConstraints:
    """Exchange-side minimums / precision for sizing checks."""

    min_amount: float | None = None
    min_cost: float | None = None
    amount_precision: int | None = None
    price_precision: int | None = None
    taker_fee_pct: float | None = None  # percent, e.g. 0.1 = 0.1%


@dataclass(slots=True)
class EquityTracker:
    """Daily loss and drawdown tracker with explicit day boundary.

    Survives process restart when start-of-day equity is restored from storage
    (Phase 4 provides the in-memory structure; persistence is optional).
    """

    day_id: str  # e.g. "2026-08-26" UTC
    start_of_day_equity: float
    peak_equity: float
    current_equity: float
    consecutive_losses: int = 0

    @property
    def daily_pnl(self) -> float:
        return self.current_equity - self.start_of_day_equity

    @property
    def daily_loss_pct(self) -> float:
        if self.start_of_day_equity <= 0:
            return 0.0
        pnl = self.daily_pnl
        if pnl >= 0:
            return 0.0
        return abs(pnl) / self.start_of_day_equity * 100.0

    @property
    def drawdown_pct(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        dd = (self.peak_equity - self.current_equity) / self.peak_equity * 100.0
        return max(0.0, dd)

    def update_equity(self, equity: float) -> None:
        self.current_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity

    def record_trade_result(self, pnl: float) -> None:
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
