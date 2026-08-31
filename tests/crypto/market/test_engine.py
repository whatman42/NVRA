"""MarketDataEngine integration tests with mock adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crypto.exchanges.errors import MarketDataError, RateLimitError, TradingDisabledError
from crypto.exchanges.models import (
    ConnectionHealth,
    Market,
    MarketType,
    OHLCVBar,
    OrderBook,
    OrderBookLevel,
    Ticker,
)
from crypto.market.config import MarketDataConfig
from crypto.market.engine import MarketDataEngine
from crypto.market.quality import DataQuality
from crypto.market.timeutils import utc_now_ms


def _market(symbol: str = "BTC/USDT", base: str = "BTC", quote: str = "USDT") -> Market:
    return Market(
        exchange="binance",
        symbol=symbol,
        base_asset=base,
        quote_asset=quote,
        active=True,
        market_type=MarketType.SPOT,
        price_precision=2,
        amount_precision=6,
        minimum_amount=0.0001,
        minimum_cost=10.0,
        maker_fee=0.001,
        taker_fee=0.001,
    )


def _ticker(ts: int | None = None) -> Ticker:
    return Ticker(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=ts if ts is not None else utc_now_ms(),
        bid=42000.0,
        ask=42001.0,
        last=42000.5,
        high=43000.0,
        low=41000.0,
        volume=100.0,
        quote_volume=4_200_000.0,
    )


def _bars(n: int = 5, start: int | None = None, interval: int = 60_000) -> list[OHLCVBar]:
    t0 = start if start is not None else (utc_now_ms() // interval) * interval - n * interval
    return [
        OHLCVBar(
            timestamp_ms=t0 + i * interval,
            open=100 + i,
            high=110 + i,
            low=90 + i,
            close=105 + i,
            volume=1.0 + i,
        )
        for i in range(n)
    ]


def _book(ts: int | None = None) -> OrderBook:
    return OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=ts if ts is not None else utc_now_ms(),
        bids=(OrderBookLevel(42000.0, 1.5),),
        asks=(OrderBookLevel(42001.0, 1.2),),
    )


@pytest.fixture
def mock_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.exchange_id = "binance"
    adapter.health_check.return_value = ConnectionHealth.CONNECTED
    adapter.fetch_markets.return_value = [_market()]
    adapter.fetch_ticker.return_value = _ticker()
    adapter.fetch_ohlcv.return_value = _bars()
    adapter.fetch_order_book.return_value = _book()
    adapter.fetch_balance.return_value = []
    return adapter


@pytest.fixture
def engine(mock_adapter: MagicMock) -> MarketDataEngine:
    cfg = MarketDataConfig(
        max_symbols=5,
        max_candles_per_key=50,
        ticker_stale_ms=60_000,
        orderbook_stale_ms=60_000,
        ohlcv_stale_bars=10,
        min_poll_interval_ms=0,  # disable sleep in tests
        cache_ttl_ms=0,
    )
    eng = MarketDataEngine(mock_adapter, cfg)
    eng.load_markets()
    return eng


def test_load_markets_builds_symbol_map(engine: MarketDataEngine) -> None:
    ns = engine.resolve_symbol("BTC/USDT")
    assert ns.base == "BTC"
    assert ns.quote == "USDT"


def test_get_ticker(engine: MarketDataEngine, mock_adapter: MagicMock) -> None:
    snap = engine.get_ticker("BTC/USDT", force_refresh=True)
    assert snap.ticker.last == 42000.5
    assert snap.quality.quality is DataQuality.COMPLETE
    assert snap.symbol.symbol == "BTC/USDT"
    mock_adapter.fetch_ticker.assert_called()


def test_ticker_cache_hit(engine: MarketDataEngine, mock_adapter: MagicMock) -> None:
    engine.get_ticker("BTC/USDT", force_refresh=True)
    mock_adapter.fetch_ticker.reset_mock()
    snap = engine.get_ticker("BTC/USDT", use_cache=True)
    assert snap.ticker.last == 42000.5
    mock_adapter.fetch_ticker.assert_not_called()
    assert engine.metrics.cache_hits >= 1


def test_stale_ticker(engine: MarketDataEngine, mock_adapter: MagicMock) -> None:
    old = _ticker(ts=utc_now_ms() - 120_000)
    mock_adapter.fetch_ticker.return_value = old
    # tighten stale threshold
    object.__setattr__(
        engine,
        "_config",
        MarketDataConfig(
            ticker_stale_ms=10_000,
            min_poll_interval_ms=0,
            cache_ttl_ms=0,
        ),
    )
    snap = engine.get_ticker("BTC/USDT", force_refresh=True)
    assert snap.quality.quality is DataQuality.STALE


def test_get_ohlcv_valid(engine: MarketDataEngine) -> None:
    snap = engine.get_ohlcv("BTC/USDT", "1m", force_refresh=True)
    assert len(snap.bars) >= 1
    assert snap.quality.is_usable
    assert snap.timeframe == "1m"


def test_ohlcv_gap_detected(engine: MarketDataEngine, mock_adapter: MagicMock) -> None:
    t0 = (utc_now_ms() // 60_000) * 60_000 - 300_000
    gapped = [
        OHLCVBar(t0, 100, 110, 90, 105, 1),
        OHLCVBar(t0 + 60_000, 105, 115, 95, 110, 1),
        OHLCVBar(t0 + 180_000, 110, 120, 100, 115, 1),  # missing +120s
    ]
    mock_adapter.fetch_ohlcv.return_value = gapped
    snap = engine.get_ohlcv("BTC/USDT", "1m", force_refresh=True)
    assert snap.quality.quality in (DataQuality.GAP_DETECTED, DataQuality.STALE)
    assert len(snap.quality.missing_timestamps_ms) >= 1


def test_ohlcv_invalid_rejected(engine: MarketDataEngine, mock_adapter: MagicMock) -> None:
    mock_adapter.fetch_ohlcv.return_value = [
        OHLCVBar(utc_now_ms() - 60_000, 0, 0, 0, 0, -1),
    ]
    with pytest.raises(MarketDataError):
        engine.get_ohlcv("BTC/USDT", "1m", force_refresh=True)


def test_order_book(engine: MarketDataEngine) -> None:
    snap = engine.get_order_book("BTC/USDT", force_refresh=True)
    assert snap.book.bids[0].price == 42000.0
    assert snap.quality.quality is DataQuality.COMPLETE


def test_crossed_book_from_adapter_already_rejected() -> None:
    # Phase 2 adapter rejects crossed books; engine also marks INVALID if seen

    # Use engine quality path directly
    book = OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=utc_now_ms(),
        bids=(OrderBookLevel(43000.0, 1.0),),
        asks=(OrderBookLevel(42000.0, 1.0),),
    )
    adapter = MagicMock()
    adapter.exchange_id = "binance"
    adapter.fetch_markets.return_value = [_market()]
    adapter.fetch_order_book.return_value = book
    eng = MarketDataEngine(adapter, MarketDataConfig(min_poll_interval_ms=0, cache_ttl_ms=0))
    eng.load_markets()
    with pytest.raises(MarketDataError, match="invalid order book|crossed"):
        eng.get_order_book("BTC/USDT", force_refresh=True)


def test_rate_limit_counted(engine: MarketDataEngine, mock_adapter: MagicMock) -> None:
    mock_adapter.fetch_ticker.side_effect = RateLimitError("slow down", exchange_id="binance")
    with pytest.raises(RateLimitError):
        engine.get_ticker("BTC/USDT", force_refresh=True)
    assert engine.metrics.rate_limit_events >= 1
    assert engine.metrics.request_failures >= 1


def test_metrics_snapshot(engine: MarketDataEngine) -> None:
    engine.get_ticker("BTC/USDT", force_refresh=True)
    snap = engine.metrics_snapshot()
    assert "cache" in snap
    assert "health" in snap


def test_cache_bounds_enforced(engine: MarketDataEngine, mock_adapter: MagicMock) -> None:
    # Fill beyond max_candles_per_key
    many = _bars(n=200)
    mock_adapter.fetch_ohlcv.return_value = many
    cfg = MarketDataConfig(max_candles_per_key=10, min_poll_interval_ms=0, cache_ttl_ms=0)
    eng = MarketDataEngine(mock_adapter, cfg)
    eng.load_markets()
    snap = eng.get_ohlcv("BTC/USDT", "1m", force_refresh=True)
    assert len(snap.bars) <= 10


def test_no_trading_via_engine(engine: MarketDataEngine, mock_adapter: MagicMock) -> None:
    # Engine must not expose order execution APIs
    assert not hasattr(MarketDataEngine, "create_order")
    assert not hasattr(engine, "create_order")
    # Real adapters still raise TradingDisabledError (Phase 2 invariant)
    from crypto.core.credentials import ExchangeCredentials, InMemoryCredentialStore
    from crypto.core.types import SecretStr
    from crypto.exchanges.binance import BinanceAdapter

    store = InMemoryCredentialStore()
    store.set(
        ExchangeCredentials(
            exchange_id="binance",
            account_id="default",
            api_key=SecretStr("dummy_key_12345678"),
            api_secret=SecretStr("dummy_secret_abcdefgh"),
        )
    )
    real = BinanceAdapter(store)
    with pytest.raises(TradingDisabledError):
        real.create_order("BTC/USDT", "buy", "market", 0.01)


def test_multi_exchange_ids() -> None:
    for eid in ("binance", "tokocrypto", "indodax"):
        adapter = MagicMock()
        adapter.exchange_id = eid
        adapter.fetch_markets.return_value = [
            _market() if eid != "indodax" else _market("BTC/IDR", "BTC", "IDR")
        ]
        adapter.health_check.return_value = ConnectionHealth.CONNECTED
        eng = MarketDataEngine(adapter, MarketDataConfig(min_poll_interval_ms=0))
        eng.load_markets()
        assert eng.exchange_id == eid
