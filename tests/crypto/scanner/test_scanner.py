"""Asset-first scanner and ranking."""

from __future__ import annotations

from crypto.ensemble import EnsembleEngine
from crypto.exchanges.models import Market, MarketType, Ticker
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.portfolio.models import AccountKey, AssetHolding
from crypto.scanner import (
    OpportunityScanner,
    ReasonCode,
    ScannerConfig,
    build_reachable_universe,
    opportunity_to_proposal,
)


def _market(sym: str, base: str, quote: str, min_cost: float = 10.0) -> Market:
    return Market(
        exchange="binance",
        symbol=sym,
        base_asset=base,
        quote_asset=quote,
        active=True,
        market_type=MarketType.SPOT,
        price_precision=2,
        amount_precision=6,
        minimum_amount=0.001,
        minimum_cost=min_cost,
        maker_fee=0.001,
        taker_fee=0.001,
    )


def test_universe_balance_filter() -> None:
    acct = AccountKey("binance", "default")
    holdings = (AssetHolding(acct, "USDT", 1000.0, 0.0, 1000.0),)
    markets = [
        _market("BTC/USDT", "BTC", "USDT"),
        _market("ETH/USDT", "ETH", "USDT"),
        _market("BTC/IDR", "BTC", "IDR"),
    ]
    u = build_reachable_universe(markets, holdings, acct)
    syms = {r.market.symbol for r in u}
    assert "BTC/USDT" in syms
    assert "ETH/USDT" in syms
    assert "BTC/IDR" not in syms


def test_no_balance_empty() -> None:
    acct = AccountKey("binance")
    u = build_reachable_universe([_market("BTC/USDT", "BTC", "USDT")], (), acct)
    assert u == []


def test_scan_respects_limits() -> None:
    eng = EnsembleEngine([])  # no models — still filters
    cfg = ScannerConfig(
        max_universe=50,
        max_candidates=10,
        max_ml_candidates=5,
        max_predictions_per_cycle=3,
        max_opportunities=2,
        min_opportunity_score=0.0,
    )
    scanner = OpportunityScanner(eng, config=cfg)
    acct = AccountKey("binance", "default")
    holdings = [AssetHolding(acct, "USDT", 5000.0, 0.0, 5000.0)]
    markets = [_market(f"C{i}/USDT", f"C{i}", "USDT") for i in range(20)]

    def get_ticker(ex: str, sym: str):
        return (
            Ticker(
                exchange=ex,
                symbol=sym,
                timestamp_ms=1,
                bid=99.0,
                ask=101.0,
                last=100.0,
                high=None,
                low=None,
                volume=None,
                quote_volume=None,
            ),
            DataQualityReport(quality=DataQuality.COMPLETE),
        )

    opps = scanner.scan(
        exchange_id="binance",
        account_id="default",
        markets=markets,
        holdings=holdings,
        get_ticker=get_ticker,
    )
    assert len(opps) <= 2
    assert scanner.telemetry.asset_filtered > 0


def test_high_spread_filtered() -> None:
    eng = EnsembleEngine([])
    cfg = ScannerConfig(max_spread_pct=0.5, min_opportunity_score=0.0)
    scanner = OpportunityScanner(eng, config=cfg)
    acct = AccountKey("binance", "default")
    holdings = [AssetHolding(acct, "USDT", 1000.0, 0.0, 1000.0)]
    markets = [_market("BTC/USDT", "BTC", "USDT")]

    def get_ticker(ex: str, sym: str):
        return (
            Ticker(
                exchange=ex,
                symbol=sym,
                timestamp_ms=1,
                bid=90.0,
                ask=110.0,  # huge spread
                last=100.0,
                high=None,
                low=None,
                volume=None,
                quote_volume=None,
            ),
            DataQualityReport(quality=DataQuality.COMPLETE),
        )

    opps = scanner.scan(
        exchange_id="binance",
        account_id="default",
        markets=markets,
        holdings=holdings,
        get_ticker=get_ticker,
    )
    assert opps == []
    assert scanner.telemetry.spread_filtered >= 1


def test_proposal_bridge_none_without_ensemble() -> None:
    from crypto.market.quality import DataQuality
    from crypto.scanner.opportunity import Feasibility, Opportunity

    opp = Opportunity(
        exchange_id="binance",
        account_id="default",
        symbol="BTC/USDT",
        base_asset="BTC",
        quote_asset="USDT",
        native_symbol="BTC/USDT",
        available_quote=1000.0,
        available_base=0.0,
        market_quality=DataQuality.COMPLETE,
        spread_pct=0.1,
        liquidity_score=0.5,
        volatility=0.01,
        ensemble=None,
        opportunity_score=0.5,
        feasibility=Feasibility.FEASIBLE,
        reason_codes=(ReasonCode.PASSED_FILTERS,),
    )
    assert opportunity_to_proposal(opp) is None
