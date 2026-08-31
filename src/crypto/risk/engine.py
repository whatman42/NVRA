"""Risk Engine — final safety gate before any future execution.

Phase 4 evaluates TradeProposal and returns RiskDecision.
It never calls create_order / cancel_order.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from crypto.market.quality import DataQuality, DataQualityReport
from crypto.portfolio.models import PortfolioSnapshot, ReconciliationResult
from crypto.risk.models import (
    EquityTracker,
    MarketConstraints,
    RejectReason,
    RiskDecision,
    RiskVerdict,
    SafetyMode,
    Side,
    TradeProposal,
)
from crypto.risk.policy import RiskPolicy
from crypto.risk.sizing import compute_position_size, meets_exchange_minimums

logger = logging.getLogger(__name__)


def utc_day_id(now_ms: int | None = None) -> str:
    if now_ms is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


class RiskEngine:
    """Deterministic risk authority. Hardware profile never mutates policy."""

    def __init__(
        self,
        policy: RiskPolicy | None = None,
        *,
        safety_mode: SafetyMode = SafetyMode.NORMAL,
    ) -> None:
        self._policy = policy or RiskPolicy()
        self._policy.validate()
        self._safety_mode = safety_mode
        self._tracker: EquityTracker | None = None
        self._reconciliation_ok = True

    @property
    def policy(self) -> RiskPolicy:
        return self._policy

    @property
    def safety_mode(self) -> SafetyMode:
        return self._safety_mode

    def set_safety_mode(self, mode: SafetyMode) -> None:
        self._safety_mode = mode
        logger.info("safety_mode=%s", mode.name)

    def set_reconciliation_ok(self, ok: bool) -> None:
        self._reconciliation_ok = ok

    def update_equity_tracker(self, equity: float, *, now_ms: int | None = None) -> EquityTracker:
        day = utc_day_id(now_ms)
        if self._tracker is None or self._tracker.day_id != day:
            self._tracker = EquityTracker(
                day_id=day,
                start_of_day_equity=equity,
                peak_equity=equity,
                current_equity=equity,
            )
        else:
            self._tracker.update_equity(equity)
        return self._tracker

    def load_equity_tracker(self, tracker: EquityTracker) -> None:
        """Restore tracker after restart (persistence is caller's job)."""
        self._tracker = tracker

    def evaluate(
        self,
        proposal: TradeProposal,
        portfolio: PortfolioSnapshot,
        *,
        market_quality: DataQualityReport | None = None,
        constraints: MarketConstraints | None = None,
        entry_price: float | None = None,
        exchange_available: bool = True,
    ) -> RiskDecision:
        """Evaluate a hypothetical trade. Never submits orders."""
        price = entry_price or proposal.requested_price
        current_exposure = portfolio.exposure.gross

        def _blocked(reason: RejectReason, msg: str, score: float = 1.0) -> RiskDecision:
            return RiskDecision(
                verdict=RiskVerdict.BLOCKED,
                reason=reason,
                message=msg,
                risk_score=score,
                allowed_quantity=0.0,
                allowed_notional=0.0,
                current_exposure=current_exposure,
                projected_exposure=current_exposure,
                proposal=proposal,
            )

        def _rejected(reason: RejectReason, msg: str, score: float = 0.8) -> RiskDecision:
            return RiskDecision(
                verdict=RiskVerdict.REJECTED,
                reason=reason,
                message=msg,
                risk_score=score,
                allowed_quantity=0.0,
                allowed_notional=0.0,
                current_exposure=current_exposure,
                projected_exposure=current_exposure,
                proposal=proposal,
            )

        # --- Safety mode / kill switch ---
        if self._safety_mode is SafetyMode.EMERGENCY_STOP:
            return _blocked(RejectReason.KILL_SWITCH, "EMERGENCY_STOP active")
        if self._safety_mode is SafetyMode.BLOCK_NEW_ENTRIES and proposal.side is Side.BUY:
            return _blocked(RejectReason.SAFETY_MODE, "BLOCK_NEW_ENTRIES: new buys blocked")
        if self._safety_mode is SafetyMode.REDUCE_ONLY and proposal.side is Side.BUY:
            return _blocked(
                RejectReason.SAFETY_MODE, "REDUCE_ONLY: only risk-reducing sells allowed"
            )

        # --- Exchange availability ---
        if not exchange_available:
            return _blocked(RejectReason.EXCHANGE_UNAVAILABLE, "exchange unavailable")

        # --- Reconciliation ---
        if not self._reconciliation_ok:
            return _blocked(
                RejectReason.RECONCILIATION_MISMATCH,
                "local/exchange state mismatch — resolve before trading",
            )

        # --- Proposal sanity ---
        if proposal.requested_quantity < 0:
            return _rejected(RejectReason.INVALID_PROPOSAL, "negative quantity")
        if price is None or price <= 0:
            return _rejected(RejectReason.INVALID_PROPOSAL, "missing or invalid price")

        # --- Market data quality gate ---
        if market_quality is not None:
            q = market_quality.quality
            if q is DataQuality.INVALID and self._policy.reject_invalid_data:
                return _rejected(
                    RejectReason.INVALID_MARKET_DATA,
                    f"market data INVALID: {market_quality.reasons}",
                )
            if q is DataQuality.STALE and self._policy.reject_stale_data:
                return _rejected(
                    RejectReason.STALE_MARKET_DATA,
                    f"market data STALE: {market_quality.reasons}",
                )
            if q is DataQuality.UNKNOWN and self._policy.reject_unknown_data:
                return _rejected(
                    RejectReason.UNKNOWN_MARKET_DATA,
                    f"market data UNKNOWN: {market_quality.reasons}",
                )

        # --- Daily loss / drawdown / consecutive losses ---
        tracker = self.update_equity_tracker(portfolio.equity)
        if tracker.daily_loss_pct >= self._policy.max_daily_loss_pct:
            return _blocked(
                RejectReason.DAILY_LOSS_LIMIT,
                f"daily loss {tracker.daily_loss_pct:.2f}% >= {self._policy.max_daily_loss_pct}%",
            )
        if tracker.drawdown_pct >= self._policy.max_drawdown_pct:
            return _blocked(
                RejectReason.DRAWDOWN_LIMIT,
                f"drawdown {tracker.drawdown_pct:.2f}% >= {self._policy.max_drawdown_pct}%",
            )
        if tracker.consecutive_losses >= self._policy.max_consecutive_losses:
            return _blocked(
                RejectReason.CONSECUTIVE_LOSSES,
                f"consecutive losses {tracker.consecutive_losses}",
            )

        # --- Concurrent positions (new entries only) ---
        if proposal.side is Side.BUY:
            open_count = portfolio.open_position_count()
            # If already in this symbol, don't count as new concurrent
            already = any(
                p.symbol == proposal.symbol and p.account == proposal.account
                for p in portfolio.positions
            )
            if not already and open_count >= self._policy.max_concurrent_positions:
                return _rejected(
                    RejectReason.MAX_CONCURRENT_POSITIONS,
                    f"open positions {open_count} >= max {self._policy.max_concurrent_positions}",
                )

        # --- Position sizing ---
        sym_exp = portfolio.exposure.by_symbol.get(proposal.symbol, 0.0)
        exch_exp = portfolio.exposure.by_exchange.get(proposal.exchange_id, 0.0)
        sizing = compute_position_size(
            equity=portfolio.equity,
            available_balance=portfolio.available_balance,
            entry_price=price,
            policy=self._policy,
            constraints=constraints,
            stop_price=proposal.stop_price,
            existing_symbol_exposure=sym_exp,
            existing_exchange_exposure=exch_exp,
            existing_portfolio_exposure=portfolio.exposure.gross,
        )

        allowed_qty = min(proposal.requested_quantity, sizing.max_quantity)
        if proposal.requested_quantity == 0:
            # "max size" request: use engine size
            allowed_qty = sizing.max_quantity

        allowed_qty = max(0.0, allowed_qty)
        allowed_notional = allowed_qty * price

        if allowed_qty <= 0 or allowed_notional <= 0:
            return _rejected(
                RejectReason.ZERO_SIZE,
                f"sized to zero (limited by {sizing.limited_by})",
            )

        # --- Exchange minimums (never round up past risk) ---
        if not meets_exchange_minimums(allowed_qty, price, constraints):
            return _rejected(
                RejectReason.ORDER_BELOW_MINIMUM,
                "allowed size below exchange minimum amount/cost; "
                "refusing to increase size beyond risk limits",
            )

        # --- Available balance check ---
        fee_pct = (
            constraints.taker_fee_pct
            if constraints and constraints.taker_fee_pct is not None
            else self._policy.default_taker_fee_pct
        )
        total_cost = allowed_notional * (
            1.0 + (fee_pct + self._policy.default_slippage_pct) / 100.0
        )
        if proposal.side is Side.BUY and total_cost > portfolio.available_balance:
            return _rejected(
                RejectReason.INSUFFICIENT_BALANCE,
                f"need ~{total_cost:.4f} quote, available {portfolio.available_balance:.4f}",
            )

        projected = current_exposure + (
            allowed_notional if proposal.side is Side.BUY else -allowed_notional
        )
        risk_score = min(1.0, allowed_notional / max(portfolio.equity, 1e-12))

        return RiskDecision(
            verdict=RiskVerdict.APPROVED,
            reason=RejectReason.NONE,
            message=f"approved qty={allowed_qty} notional={allowed_notional:.4f} "
            f"(limited by {sizing.limited_by})",
            risk_score=risk_score,
            allowed_quantity=allowed_qty,
            allowed_notional=allowed_notional,
            current_exposure=current_exposure,
            projected_exposure=max(0.0, projected),
            proposal=proposal,
        )

    def evaluate_circuit_breakers(
        self,
        portfolio: PortfolioSnapshot,
        *,
        market_quality: DataQualityReport | None = None,
        exchange_available: bool = True,
        reconciliation: ReconciliationResult | None = None,
        abnormal_move: bool = False,
    ) -> SafetyMode:
        """Update safety mode from portfolio / market conditions.

        Returns the resulting mode (also stored on the engine).
        """
        tracker = self.update_equity_tracker(portfolio.equity)

        if not exchange_available:
            self.set_safety_mode(SafetyMode.BLOCK_NEW_ENTRIES)
            return self._safety_mode

        if reconciliation is not None and reconciliation.has_mismatch:
            self.set_reconciliation_ok(False)
            self.set_safety_mode(SafetyMode.BLOCK_NEW_ENTRIES)
            return self._safety_mode

        if tracker.drawdown_pct >= self._policy.max_drawdown_pct:
            self.set_safety_mode(SafetyMode.EMERGENCY_STOP)
            return self._safety_mode

        if tracker.daily_loss_pct >= self._policy.max_daily_loss_pct:
            self.set_safety_mode(SafetyMode.BLOCK_NEW_ENTRIES)
            return self._safety_mode

        if market_quality is not None and market_quality.quality in (
            DataQuality.STALE,
            DataQuality.INVALID,
            DataQuality.UNKNOWN,
        ):
            self.set_safety_mode(SafetyMode.WARNING)
            return self._safety_mode

        if abnormal_move:
            self.set_safety_mode(SafetyMode.REDUCE_ONLY)
            return self._safety_mode

        if self._safety_mode in (
            SafetyMode.WARNING,
            SafetyMode.BLOCK_NEW_ENTRIES,
            SafetyMode.REDUCE_ONLY,
        ):
            # Auto-recover to NORMAL only from soft states when conditions clear
            self.set_safety_mode(SafetyMode.NORMAL)

        return self._safety_mode
