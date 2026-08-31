# Exchange Gateway

**Phase 2 — READ ONLY**

This document describes the exchange abstraction and the three initial adapters.
Live order execution is **disabled**. Calling `create_order` or `cancel_order`
raises `TradingDisabledError`.

## Supported exchanges

| exchange_id  | CCXT id     | Notes                                      |
|--------------|-------------|--------------------------------------------|
| `binance`    | `binance`   | Spot by default                            |
| `tokocrypto` | `tokocrypto`| Indonesia; capability set depends on CCXT  |
| `indodax`    | `indodax`   | Indonesia; some endpoints differ           |

## Capabilities (Phase 2)

| Capability        | Status                                      |
|-------------------|---------------------------------------------|
| connect / auth    | Yes                                         |
| health_check      | Yes (lightweight)                           |
| fetch_markets     | Yes                                         |
| fetch_balance     | Yes                                         |
| fetch_ticker      | Yes                                         |
| fetch_order_book  | Yes                                         |
| fetch_ohlcv       | Yes when exchange supports it               |
| fetch_open_orders | Yes when exchange supports it               |
| fetch_order       | Yes when exchange supports it               |
| fetch_my_trades   | Yes when exchange supports it               |
| fetch_positions   | Empty list on spot; error only if forced    |
| create_order      | **DISABLED** — raises TradingDisabledError  |
| cancel_order      | **DISABLED** — raises TradingDisabledError  |
| withdrawal        | **Never called**                            |

Unsupported operations raise `UnsupportedCapabilityError` rather than inventing behaviour.

## Credential requirements

1. Store API key + secret via Phase 1 `CredentialStore` under `(exchange_id, account_id)`.
2. Prefer keys with **Withdrawal = DISABLED**.
3. Trading permission may be present on the key; the adapter still will not place orders in Phase 2.
4. Never pass raw secrets through application layers — adapters load them from the store on `connect()`.

## Permission validation

`validate_permissions()` performs **read-only** probes:

- market data (public ticker)
- account read (`fetch_balance`)
- trading / withdrawal status when the exchange exposes them (otherwise `UNKNOWN`)

No order is submitted to test trading permission.

If withdrawal appears enabled, the report includes a **HIGH** severity warning string.

## Rate limiting & errors

- CCXT `enableRateLimit=True` is set on every client.
- Transient network errors use bounded retry (max 2) with short backoff.
- Authentication and rate-limit errors are **not** retried in a loop.
- CCXT exceptions are translated into:

  `AuthenticationError`, `PermissionError`, `RateLimitError`, `NetworkError`,
  `ExchangeUnavailableError`, `MarketDataError`, `UnsupportedCapabilityError`,
  `TradingDisabledError`, `CredentialMissingError`.

## Market normalisation

Adapters map exchange responses into:

- `Market` — symbol, base/quote, precision, min amount/cost, fees (None when unknown)
- `AssetBalance` — free / used / total (no assumption that total = free + used)
- `Ticker`, `OrderBook`, `OHLCVBar`, `OpenOrder`, `Trade`, `Position`

Invalid data (NaN, Inf, negative prices/volumes, crossed books) raises `MarketDataError`.

## Architecture boundary

```
CredentialStore → ExchangeAdapter → CRYPTO domain models
                       ↑
                     CCXT  (isolated inside src/crypto/exchanges/)
```

Core, risk, and future ML packages must not import CCXT types directly.

## Known differences

- **Tokocrypto / INDODAX**: CCXT coverage and precision fields may be incomplete; missing fields are `None`, missing methods raise `UnsupportedCapabilityError`.
- **Binance**: richest metadata; spot default.
- Public market data may work without credentials on some exchanges; balance and private endpoints require a valid key.

## Live tests

Optional live tests (not run in CI) may be enabled later with an explicit environment flag.
Even then, **orders must never be submitted**.
