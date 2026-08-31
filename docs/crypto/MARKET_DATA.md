# Market Data Engine

**Phase 3 — market data only (READ ONLY)**

No order execution. No trading decisions. No ML. No portfolio risk decisions.

## Architecture

```
ExchangeAdapter (Phase 2)
        ↓
Market Data Engine
        ↓
Validation → Normalization → Bounded Cache → Quality Report
        ↓
Consumers (future): Portfolio · Risk · ML · Backtesting · GUI
```

- One `MarketDataEngine` instance per `ExchangeAdapter`.
- Consumers use **normalized symbols** (`BTC/USDT`) and domain models from Phase 2.
- CCXT never leaks past the exchange package.

## Normalized symbols

```text
native (exchange)  →  NormalizedSymbol(base, quote, exchange_id, native)
                      .symbol == "BTC/USDT"
```

Supported forms: `BTC/USDT`, `BTC-USDT`, `BTC_USDT`, and metadata base/quote from markets.

## Time

- All internal timestamps are **UTC milliseconds** since Unix epoch.
- Exchange timestamps are normalized at the adapter boundary.
- Future timestamps (beyond tolerance) and missing timestamps are rejected or marked.

## Supported data

| Data        | Method            | Notes                          |
|-------------|-------------------|--------------------------------|
| Markets     | `load_markets()`  | Builds symbol map              |
| Ticker      | `get_ticker()`    | Cache + stale detection        |
| OHLCV       | `get_ohlcv()`     | Validation, gaps, duplicates   |
| Order book  | `get_order_book()`| Crossed-book rejection         |
| Balance     | `get_balance()`   | Pass-through (read-only)       |

## Timeframes

Default configurable set:

`1m`, `5m`, `15m`, `1h`, `4h`

Subscriptions are config-driven — the engine does **not** download every timeframe for every symbol automatically.

## Data quality

```text
DataQuality: COMPLETE | PARTIAL | GAP_DETECTED | STALE | INVALID | UNKNOWN
```

Each snapshot (`TickerSnapshot`, `OHLCVSnapshot`, `OrderBookSnapshot`) carries a `DataQualityReport` with reasons, missing timestamps, and duplicate/invalid counts.

**Gaps:** detected, never invented.  
**Duplicates:** collapsed by timestamp (last wins).  
**Stale:** configurable thresholds (`ticker_stale_ms`, `orderbook_stale_ms`, `ohlcv_stale_bars × timeframe`).

## Cache / memory policy

Bounded in-memory only (no DuckDB/Redis/Kafka in Phase 3):

| Structure   | Bound                         |
|-------------|-------------------------------|
| Tickers     | `max_ticker_entries` (default 50) |
| Order books | `max_orderbook_entries` (30)  |
| OHLCV keys  | `max_symbols × timeframes`    |
| Candles/key | `max_candles_per_key` (500)   |
| TTL         | `cache_ttl_ms` (5 min)        |

LRU eviction when capacity is exceeded. Designed for i3 / <4 GB RAM / HDD.

Future hardware governor (Phase 9) can tighten these via `MarketDataConfig`.

## Rate limiting

- Respects Phase 2 adapter rate-limit handling.
- Per-key minimum poll interval (`min_poll_interval_ms`).
- Prefers cache when data is still fresh.
- Rate-limit and failure events counted in `MarketDataMetrics`.

## REST behaviour

Phase 3 uses REST polling through the adapter. Interfaces are feed-agnostic so a future WebSocket source can push into the same cache/quality path.

## Failure behaviour

```text
CONNECTED → DEGRADED → STALE
```

No fabricated prices or candles. Consumers distinguish no data / stale / invalid / unavailable via `DataQuality` and exceptions.

## Security

Same rules as Phase 1–2: no API secrets in logs, CredentialStore only, trading methods remain disabled on adapters.

## Metrics

`engine.metrics_snapshot()` exposes last update times, ages, gaps, duplicates, invalids, request failures, rate-limit events, and cache hit/miss counts.
