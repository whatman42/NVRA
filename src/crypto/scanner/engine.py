"""Asset-aware opportunity scanner — never submits orders."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from crypto.ensemble.engine import EnsembleEngine
from crypto.exchanges.models import Market, OHLCVBar, Ticker
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.portfolio.models import AccountKey, AssetHolding, PortfolioSnapshot
from crypto.scanner.config import ScannerConfig
from crypto.scanner.filters import (
    edge_covers_costs,
    filter_inactive,
    filter_min_order,
    filter_quality,
    filter_spread,
)
from crypto.scanner.opportunity import (
    Opportunity,
    ReasonCode,
    ScanTelemetry,
)
from crypto.scanner.scoring import score_opportunity
from crypto.scanner.universe import ReachableMarket, build_reachable_universe

# Callables supplied by host for market data (keeps scanner free of exchange IO)
TickerFn = Callable[[str, str], tuple[Ticker | None, DataQualityReport | None]]
OhlcvFn = Callable[[str, str], Sequence[OHLCVBar] | None]


class OpportunityScanner:
    """Cheap filters → bounded ML → ranked opportunities."""

    def __init__(
        self,
        ensemble: EnsembleEngine,
        *,
        config: ScannerConfig | None = None,
    ) -> None:
        self._ensemble = ensemble
        self._config = config or ScannerConfig()
        self._config.validate()
        self.telemetry = ScanTelemetry()

    def scan(
        self,
        *,
        exchange_id: str,
        account_id: str,
        markets: Sequence[Market],
        holdings: Sequence[AssetHolding],
        portfolio: PortfolioSnapshot | None = None,
        get_ticker: TickerFn | None = None,
        get_ohlcv: OhlcvFn | None = None,
    ) -> list[Opportunity]:
        self.telemetry = ScanTelemetry()
        account = AccountKey(exchange_id, account_id)
        self.telemetry.markets_scanned = len(markets)

        reachable = build_reachable_universe(
            markets,
            holdings,
            account,
            max_hops=self._config.max_conversion_hops,
            max_universe=self._config.max_universe,
        )
        self.telemetry.asset_filtered = len(reachable)

        # Existing exposure symbols
        exposed: set[str] = set()
        if portfolio:
            for p in portfolio.positions:
                if p.account == account:
                    exposed.add(p.symbol)

        candidates: list[
            tuple[ReachableMarket, list[ReasonCode], float | None, float | None, DataQuality]
        ] = []
        for rm in reachable:
            reasons: list[ReasonCode] = [ReasonCode.BALANCE_AVAILABLE]
            ok, r = filter_inactive(rm)
            if not ok:
                continue
            reasons.extend(r)

            spread: float | None = None
            mid: float | None = None
            quality = DataQuality.COMPLETE
            if get_ticker:
                ticker, qreport = get_ticker(exchange_id, rm.market.symbol)
                if qreport:
                    quality = qreport.quality
                ok_q, rq = filter_quality(quality)
                if not ok_q:
                    self.telemetry.quality_rejected += 1
                    continue
                reasons.extend(rq)
                if ticker and ticker.bid and ticker.ask and ticker.bid > 0:
                    mid = (ticker.bid + ticker.ask) / 2.0
                    spread = (ticker.ask - ticker.bid) / mid * 100.0
                elif ticker and ticker.last:
                    mid = ticker.last

            ok_s, rs = filter_spread(spread, self._config)
            if not ok_s:
                self.telemetry.spread_filtered += 1
                continue
            reasons.extend(rs)

            candidates.append((rm, reasons, spread, mid, quality))
            if len(candidates) >= self._config.max_candidates:
                break

        # ML only on top slice
        ml_slice = candidates[: self._config.max_ml_candidates]
        self.telemetry.ml_candidates = len(ml_slice)

        opportunities: list[Opportunity] = []
        for rm, reasons, spread, mid, quality in ml_slice:
            if len(opportunities) >= self._config.max_predictions_per_cycle:
                break

            ensemble = None
            if get_ohlcv and self._ensemble.model_count > 0:
                bars = get_ohlcv(exchange_id, rm.market.symbol)
                if bars and len(bars) >= 25:
                    ensemble = self._ensemble.predict(
                        rm.market.symbol,
                        bars,
                        data_quality=DataQualityReport(quality=quality),
                    )
                    self.telemetry.predictions += 1
                    if ensemble.high_disagreement:
                        reasons = list(reasons) + [ReasonCode.HIGH_DISAGREEMENT]
                    if ensemble.direction.name != "NEUTRAL" and ensemble.confidence >= 0.4:
                        reasons = list(reasons) + [ReasonCode.STRONG_SIGNAL]

            feas, fr = filter_min_order(
                rm.quote_balance,
                mid,
                rm.market.minimum_cost,
                rm.market.minimum_amount,
            )
            reasons = list(reasons) + fr

            if ensemble:
                ok_edge, er = edge_covers_costs(
                    ensemble.expected_return,
                    spread,
                    self._config.default_fee_pct,
                    self._config.default_slippage_pct,
                )
                if not ok_edge:
                    reasons = list(reasons) + er

            has_exp = rm.market.symbol in exposed
            if has_exp:
                reasons = list(reasons) + [ReasonCode.DUPLICATE_EXPOSURE]

            liq = 0.5 if mid else 0.2
            sc = score_opportunity(
                ensemble,
                spread_pct=spread,
                liquidity_score=liq,
                available_quote=rm.quote_balance,
                has_existing_exposure=has_exp,
                fee_pct=self._config.default_fee_pct,
                slippage_pct=self._config.default_slippage_pct,
            )
            if sc < self._config.min_opportunity_score and ensemble is None:
                continue

            reasons = list(reasons) + [ReasonCode.PASSED_FILTERS, ReasonCode.RANKED]
            opportunities.append(
                Opportunity(
                    exchange_id=exchange_id,
                    account_id=account_id,
                    symbol=rm.market.symbol,
                    base_asset=(rm.market.base_asset or "").upper(),
                    quote_asset=(rm.market.quote_asset or "").upper(),
                    native_symbol=rm.market.symbol,
                    available_quote=rm.quote_balance,
                    available_base=rm.base_balance,
                    market_quality=quality,
                    spread_pct=spread,
                    liquidity_score=liq,
                    volatility=ensemble.volatility_estimate if ensemble else 0.0,
                    ensemble=ensemble,
                    opportunity_score=sc,
                    feasibility=feas,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    mid_price=mid,
                    min_cost=rm.market.minimum_cost,
                    estimated_fee_pct=self._config.default_fee_pct,
                )
            )

        opportunities.sort(key=lambda o: o.opportunity_score, reverse=True)
        final = opportunities[: self._config.max_opportunities]
        self.telemetry.final_opportunities = len(final)
        return final
