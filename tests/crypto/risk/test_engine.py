"""RiskEngine decisions, circuit breakers, quality gate."""

from __future__ import annotations

from crypto.exchanges.models import AssetBalance
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.portfolio import AccountKey, build_holdings, build_portfolio
from crypto.risk import (
    MarketConstraints,
    RejectReason,
    RiskEngine,
    RiskPolicy,
    RiskVerdict,
    SafetyMode,
    Side,
    TradeProposal,
)


def _portfolio(equity_quote: float = 10_000.0, quote: str = "USDT") -> object:
    acct = AccountKey("binance", "default")
    holds = build_holdings(acct, [AssetBalance(quote, equity_quote, 0.0, equity_quote)])
    return build_portfolio(accounts_holdings={acct: holds}, quote_currency=quote)


def _proposal(
    qty: float = 1.0,
    price: float = 100.0,
    side: Side = Side.BUY,
    symbol: str = "BTC/USDT",
) -> TradeProposal:
    return TradeProposal(
        exchange_id="binance",
        account_id="default",
        symbol=symbol,
        side=side,
        requested_quantity=qty,
        requested_price=price,
    )


def test_approve_normal() -> None:
    eng = RiskEngine(RiskPolicy(max_position_pct=5.0))
    pf = _portfolio(10_000.0)
    d = eng.evaluate(
        _proposal(qty=100.0, price=100.0),
        pf,
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=10.0),
    )
    assert d.verdict is RiskVerdict.APPROVED
    assert d.executable
    assert d.allowed_notional <= 500.0 * 1.01
    assert d.allowed_quantity > 0


def test_reject_stale_data() -> None:
    eng = RiskEngine()
    d = eng.evaluate(
        _proposal(),
        _portfolio(),
        market_quality=DataQualityReport(quality=DataQuality.STALE, reasons=("stale ticker",)),
    )
    assert d.verdict is RiskVerdict.REJECTED
    assert d.reason is RejectReason.STALE_MARKET_DATA
    assert not d.executable


def test_reject_invalid_data() -> None:
    eng = RiskEngine()
    d = eng.evaluate(
        _proposal(),
        _portfolio(),
        market_quality=DataQualityReport(quality=DataQuality.INVALID),
    )
    assert d.reason is RejectReason.INVALID_MARKET_DATA


def test_small_account_below_minimum() -> None:
    """Rp100.000 equity, min cost above risk-sized notional → ORDER_BELOW_MINIMUM."""
    eng = RiskEngine(RiskPolicy(max_position_pct=5.0))
    pf = _portfolio(100_000.0, quote="IDR")
    d = eng.evaluate(
        _proposal(qty=0.0, price=1_000.0),
        pf,
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.01, min_cost=15_000.0),
    )
    assert d.verdict is RiskVerdict.REJECTED
    assert d.reason is RejectReason.ORDER_BELOW_MINIMUM
    assert not d.executable


def test_kill_switch_blocks() -> None:
    eng = RiskEngine(safety_mode=SafetyMode.EMERGENCY_STOP)
    d = eng.evaluate(_proposal(), _portfolio())
    assert d.verdict is RiskVerdict.BLOCKED
    assert d.reason is RejectReason.KILL_SWITCH


def test_block_new_entries() -> None:
    eng = RiskEngine(safety_mode=SafetyMode.BLOCK_NEW_ENTRIES)
    d = eng.evaluate(_proposal(side=Side.BUY), _portfolio())
    assert d.verdict is RiskVerdict.BLOCKED
    assert d.reason is RejectReason.SAFETY_MODE


def test_drawdown_emergency_stop() -> None:
    eng = RiskEngine(RiskPolicy(max_drawdown_pct=5.0))
    t = eng.update_equity_tracker(10_000.0)
    t.peak_equity = 10_000.0
    t.current_equity = 9_000.0  # 10% drawdown
    eng.load_equity_tracker(t)
    pf = build_portfolio(
        accounts_holdings={
            AccountKey("binance"): build_holdings(
                AccountKey("binance"),
                [AssetBalance("USDT", 9_000.0, 0.0, 9_000.0)],
            )
        }
    )
    mode = eng.evaluate_circuit_breakers(pf)
    assert mode is SafetyMode.EMERGENCY_STOP


def test_reconciliation_blocks() -> None:
    eng = RiskEngine()
    eng.set_reconciliation_ok(False)
    d = eng.evaluate(
        _proposal(),
        _portfolio(),
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
    )
    assert d.verdict is RiskVerdict.BLOCKED
    assert d.reason is RejectReason.RECONCILIATION_MISMATCH


def test_exchange_unavailable() -> None:
    eng = RiskEngine()
    d = eng.evaluate(
        _proposal(),
        _portfolio(),
        exchange_available=False,
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
    )
    assert d.reason is RejectReason.EXCHANGE_UNAVAILABLE


def test_approved_quantity_never_exceeds_max() -> None:
    eng = RiskEngine(RiskPolicy(max_position_pct=5.0))
    pf = _portfolio(10_000.0)
    d = eng.evaluate(
        _proposal(qty=9999.0, price=100.0),
        pf,
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
    )
    assert d.approved
    assert d.allowed_notional <= 500.0 * 1.05
    assert d.allowed_quantity <= d.allowed_notional / 100.0 + 1e-9


def test_rejected_not_executable() -> None:
    eng = RiskEngine()
    d = eng.evaluate(
        _proposal(),
        _portfolio(),
        market_quality=DataQualityReport(quality=DataQuality.STALE),
    )
    assert not d.executable
    assert d.allowed_quantity == 0.0


def test_insufficient_balance() -> None:
    eng = RiskEngine(RiskPolicy(max_position_pct=90.0))
    pf = _portfolio(100.0)
    d = eng.evaluate(
        _proposal(qty=10.0, price=50.0),
        pf,
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
    )
    assert d.verdict in (RiskVerdict.REJECTED, RiskVerdict.APPROVED)
    if d.approved:
        assert d.allowed_notional <= 100.0 * 1.01
    else:
        assert d.reason in (
            RejectReason.INSUFFICIENT_BALANCE,
            RejectReason.ZERO_SIZE,
            RejectReason.ORDER_BELOW_MINIMUM,
        )
