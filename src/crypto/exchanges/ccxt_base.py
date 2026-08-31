"""Shared CCXT-backed adapter base (read-only).

CCXT types stay inside this module and concrete adapters.
Domain code only sees crypto.exchanges.models and crypto.exchanges.errors.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

from crypto.core.credentials import CredentialStore, ExchangeCredentials
from crypto.exchanges.base import ExchangeAdapter
from crypto.exchanges.errors import (
    AuthenticationError,
    CredentialMissingError,
    ExchangeError,
    ExchangeUnavailableError,
    MarketDataError,
    NetworkError,
    PermissionError,
    RateLimitError,
    UnsupportedCapabilityError,
)
from crypto.exchanges.models import (
    AssetBalance,
    ConnectionHealth,
    Market,
    MarketType,
    OHLCVBar,
    OpenOrder,
    OrderBook,
    OrderBookLevel,
    PermissionReport,
    PermissionStatus,
    Position,
    Ticker,
    Trade,
)
from crypto.exchanges.validation import (
    optional_finite,
    optional_non_negative,
    optional_timestamp_ms,
    require_finite,
    require_non_negative,
    require_positive,
)

logger = logging.getLogger(__name__)

# Bounded retry for transient network errors only.
_MAX_RETRIES = 2
_RETRY_BACKOFF_S = 0.5


class CcxtReadOnlyAdapter(ExchangeAdapter):
    """Base for CCXT-backed read-only adapters.

    Subclasses set:
      - exchange_id
      - _ccxt_exchange_id  (id passed to ccxt)
      - optional _ccxt_options
    """

    exchange_id: str = "unknown"
    _ccxt_exchange_id: str = "unknown"
    _ccxt_options: dict[str, Any] = {}

    def __init__(
        self,
        credential_store: CredentialStore,
        account_id: str = "default",
        *,
        sandbox: bool = False,
    ) -> None:
        self._store = credential_store
        self._account_id = account_id
        self._sandbox = sandbox
        self._client: Any = None
        self._health = ConnectionHealth.DISCONNECTED
        self._markets_loaded = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self._client is not None and self._markets_loaded:
            return
        self._health = ConnectionHealth.CONNECTING
        try:
            creds = self._load_credentials()
            self._client = self._build_client(creds)
            self._safe_call(self._client.load_markets)
            self._markets_loaded = True
            self._health = ConnectionHealth.CONNECTED
            logger.info(
                "connected exchange=%s account=%s",
                self.exchange_id,
                self._account_id,
            )
        except AuthenticationError:
            self._health = ConnectionHealth.AUTH_FAILED
            raise
        except RateLimitError:
            self._health = ConnectionHealth.RATE_LIMITED
            raise
        except (NetworkError, ExchangeUnavailableError):
            self._health = ConnectionHealth.EXCHANGE_UNAVAILABLE
            raise
        except Exception:
            self._health = ConnectionHealth.UNKNOWN
            raise

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                close = getattr(self._client, "close", None)
                if callable(close):
                    close()
            except Exception:  # noqa: BLE001 — best-effort
                logger.debug("error while closing exchange client", exc_info=True)
        self._client = None
        self._markets_loaded = False
        self._health = ConnectionHealth.DISCONNECTED

    def health_check(self) -> ConnectionHealth:
        if self._client is None:
            return ConnectionHealth.DISCONNECTED
        try:
            # Lightweight public call when possible
            if getattr(self._client, "has", {}).get("fetchStatus"):
                self._safe_call(self._client.fetch_status)
            elif getattr(self._client, "has", {}).get("fetchTime"):
                self._safe_call(self._client.fetch_time)
            else:
                # Fall back to cached markets presence
                if not self._markets_loaded:
                    return ConnectionHealth.DISCONNECTED
            self._health = ConnectionHealth.CONNECTED
            return self._health
        except RateLimitError:
            self._health = ConnectionHealth.RATE_LIMITED
            return self._health
        except AuthenticationError:
            self._health = ConnectionHealth.AUTH_FAILED
            return self._health
        except (NetworkError, ExchangeUnavailableError):
            self._health = ConnectionHealth.EXCHANGE_UNAVAILABLE
            return self._health
        except Exception:  # noqa: BLE001
            self._health = ConnectionHealth.DEGRADED
            return self._health

    # ------------------------------------------------------------------
    # Permissions (read-only probes)
    # ------------------------------------------------------------------

    def validate_permissions(self) -> PermissionReport:
        self._ensure_connected()
        warnings: list[str] = []
        authenticated = True
        market_data = PermissionStatus.UNKNOWN
        account_read = PermissionStatus.UNKNOWN
        trading = PermissionStatus.UNKNOWN
        withdrawal = PermissionStatus.UNKNOWN

        # Market data: try a public ticker if markets exist
        try:
            symbols = list(getattr(self._client, "symbols", []) or [])
            if symbols:
                self._safe_call(self._client.fetch_ticker, symbols[0])
                market_data = PermissionStatus.GRANTED
            else:
                market_data = PermissionStatus.UNKNOWN
        except AuthenticationError:
            authenticated = False
            market_data = PermissionStatus.DENIED
        except Exception:  # noqa: BLE001
            market_data = PermissionStatus.UNKNOWN

        # Account read
        try:
            self._safe_call(self._client.fetch_balance)
            account_read = PermissionStatus.GRANTED
        except (AuthenticationError, PermissionError):
            account_read = PermissionStatus.DENIED
            authenticated = authenticated and False
        except Exception:  # noqa: BLE001
            account_read = PermissionStatus.UNKNOWN

        # Trading / withdrawal: rely on exchange-reported permissions when present.
        # Never place an order to probe.
        try:
            perms = self._extract_api_permissions()
            trading = perms.get("trading", PermissionStatus.UNKNOWN)
            withdrawal = perms.get("withdrawal", PermissionStatus.UNKNOWN)
        except Exception:  # noqa: BLE001
            trading = PermissionStatus.UNKNOWN
            withdrawal = PermissionStatus.UNKNOWN

        if withdrawal is PermissionStatus.GRANTED:
            warnings.append(
                "WARNING — Withdrawal permission appears ENABLED. "
                "Strongly recommend using an API key with Withdrawal DISABLED."
            )

        return PermissionReport(
            authenticated=authenticated,
            market_data=market_data,
            account_read=account_read,
            trading=trading,
            withdrawal=withdrawal,
            warnings=tuple(warnings),
        )

    def _extract_api_permissions(self) -> dict[str, PermissionStatus]:
        """Best-effort extraction of key permissions from exchange response.

        Most spot exchanges do not expose a portable permissions API via CCXT.
        Subclasses may override. Default: all UNKNOWN.
        """
        return {
            "trading": PermissionStatus.UNKNOWN,
            "withdrawal": PermissionStatus.UNKNOWN,
        }

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def fetch_markets(self) -> Sequence[Market]:
        self._ensure_connected()
        raw_markets = getattr(self._client, "markets", None) or {}
        result: list[Market] = []
        for symbol, m in raw_markets.items():
            result.append(self._normalize_market(symbol, m))
        return result

    def fetch_balance(self) -> Sequence[AssetBalance]:
        self._ensure_connected()
        raw = self._safe_call(self._client.fetch_balance)
        return self._normalize_balances(raw)

    def fetch_ticker(self, symbol: str) -> Ticker:
        self._ensure_connected()
        raw = self._safe_call(self._client.fetch_ticker, symbol)
        return self._normalize_ticker(symbol, raw)

    def fetch_order_book(self, symbol: str, limit: int | None = None) -> OrderBook:
        self._ensure_connected()
        kwargs: dict[str, Any] = {}
        if limit is not None:
            kwargs["limit"] = limit
        raw = self._safe_call(self._client.fetch_order_book, symbol, **kwargs)
        return self._normalize_order_book(symbol, raw)

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        since_ms: int | None = None,
        limit: int | None = None,
    ) -> Sequence[OHLCVBar]:
        self._ensure_connected()
        has = getattr(self._client, "has", {})
        if not has.get("fetchOHLCV"):
            raise UnsupportedCapabilityError(
                f"{self.exchange_id} does not support fetchOHLCV",
                exchange_id=self.exchange_id,
            )
        raw = self._safe_call(
            self._client.fetch_ohlcv,
            symbol,
            timeframe=timeframe,
            since=since_ms,
            limit=limit,
        )
        return self._normalize_ohlcv(raw)

    def fetch_open_orders(self, symbol: str | None = None) -> Sequence[OpenOrder]:
        self._ensure_connected()
        has = getattr(self._client, "has", {})
        if not has.get("fetchOpenOrders"):
            raise UnsupportedCapabilityError(
                f"{self.exchange_id} does not support fetchOpenOrders",
                exchange_id=self.exchange_id,
            )
        raw = self._safe_call(self._client.fetch_open_orders, symbol)
        return [self._normalize_order(o) for o in (raw or [])]

    def fetch_order(self, order_id: str, symbol: str | None = None) -> OpenOrder:
        self._ensure_connected()
        has = getattr(self._client, "has", {})
        if not has.get("fetchOrder"):
            raise UnsupportedCapabilityError(
                f"{self.exchange_id} does not support fetchOrder",
                exchange_id=self.exchange_id,
            )
        raw = self._safe_call(self._client.fetch_order, order_id, symbol)
        return self._normalize_order(raw)

    def fetch_my_trades(
        self,
        symbol: str | None = None,
        since_ms: int | None = None,
        limit: int | None = None,
    ) -> Sequence[Trade]:
        self._ensure_connected()
        has = getattr(self._client, "has", {})
        if not has.get("fetchMyTrades"):
            raise UnsupportedCapabilityError(
                f"{self.exchange_id} does not support fetchMyTrades",
                exchange_id=self.exchange_id,
            )
        raw = self._safe_call(self._client.fetch_my_trades, symbol, since=since_ms, limit=limit)
        return [self._normalize_trade(t) for t in (raw or [])]

    def fetch_positions(self) -> Sequence[Position]:
        self._ensure_connected()
        has = getattr(self._client, "has", {})
        if not has.get("fetchPositions"):
            # Spot exchanges commonly lack this — return empty, not an error.
            return []
        raw = self._safe_call(self._client.fetch_positions)
        return [self._normalize_position(p) for p in (raw or [])]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._client is None or not self._markets_loaded:
            self.connect()

    def _load_credentials(self) -> ExchangeCredentials:
        try:
            return self._store.get(self.exchange_id, self._account_id)
        except Exception as exc:
            # Avoid leaking store exception details that might contain secrets
            raise CredentialMissingError(
                f"no credentials for exchange={self.exchange_id!r} account={self._account_id!r}",
                exchange_id=self.exchange_id,
            ) from exc

    def _build_client(self, creds: ExchangeCredentials) -> Any:
        try:
            import ccxt
        except ImportError as exc:
            raise ExchangeError(
                "ccxt package is required for exchange connectivity. "
                "Install with: pip install ccxt",
                exchange_id=self.exchange_id,
            ) from exc

        cls = getattr(ccxt, self._ccxt_exchange_id, None)
        if cls is None:
            raise ExchangeError(
                f"ccxt does not provide exchange id {self._ccxt_exchange_id!r}",
                exchange_id=self.exchange_id,
            )

        api_key = creds.api_key.get_secret_value()
        api_secret = creds.api_secret.get_secret_value()
        # Never log these values
        config: dict[str, Any] = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            **self._ccxt_options,
        }
        client = cls(config)
        if self._sandbox:
            sandbox_fn = getattr(client, "set_sandbox_mode", None)
            if not callable(sandbox_fn):
                raise UnsupportedCapabilityError(
                    f"{self.exchange_id} has no native sandbox/testnet support; "
                    "DEMO mode cannot route to production endpoints",
                    exchange_id=self.exchange_id,
                )
            try:
                sandbox_fn(True)
            except Exception as exc:  # noqa: BLE001
                raise UnsupportedCapabilityError(
                    f"{self.exchange_id} sandbox/testnet activation failed: {exc}",
                    exchange_id=self.exchange_id,
                ) from exc
        return client

    def _safe_call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Call a CCXT method with bounded retry and error translation."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — translated below
                translated = self._translate_error(exc)
                if isinstance(translated, AuthenticationError):
                    raise translated from exc
                if isinstance(translated, RateLimitError):
                    raise translated from exc
                if isinstance(translated, PermissionError):
                    raise translated from exc
                if isinstance(translated, (NetworkError, ExchangeUnavailableError)):
                    last_exc = translated
                    if attempt < _MAX_RETRIES:
                        time.sleep(_RETRY_BACKOFF_S * (attempt + 1))
                        continue
                    raise translated from exc
                raise translated from exc
        assert last_exc is not None
        raise last_exc

    def _translate_error(self, exc: Exception) -> ExchangeError:
        name = type(exc).__name__
        msg = _sanitize_message(str(exc))
        # Prefer duck-typing on CCXT exception hierarchy names
        if "Authentication" in name or "InvalidNonce" in name:
            return AuthenticationError(msg, exchange_id=self.exchange_id)
        if "Permission" in name or "Authorization" in name:
            return PermissionError(msg, exchange_id=self.exchange_id)
        if "RateLimit" in name or "DDoS" in name:
            return RateLimitError(msg, exchange_id=self.exchange_id)
        if "Network" in name or "RequestTimeout" in name or "ExchangeNotAvailable" in name:
            if "NotAvailable" in name or "Maintenance" in msg.lower():
                return ExchangeUnavailableError(msg, exchange_id=self.exchange_id)
            return NetworkError(msg, exchange_id=self.exchange_id)
        if "ExchangeNotAvailable" in name:
            return ExchangeUnavailableError(msg, exchange_id=self.exchange_id)
        return ExchangeError(msg, exchange_id=self.exchange_id)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_market(self, symbol: str, m: dict[str, Any]) -> Market:
        market_type = MarketType.UNKNOWN
        mtype = (m.get("type") or m.get("spot") and "spot") or None
        if m.get("spot") is True or mtype == "spot":
            market_type = MarketType.SPOT
        elif mtype in ("swap", "future", "margin", "option"):
            try:
                market_type = MarketType[str(mtype).upper()]
            except KeyError:
                market_type = MarketType.UNKNOWN

        precision = m.get("precision") or {}
        limits = m.get("limits") or {}
        amount_limits = limits.get("amount") or {}
        cost_limits = limits.get("cost") or {}

        def _prec(val: Any) -> int | None:
            if val is None:
                return None
            try:
                # CCXT sometimes returns decimal places as int, sometimes as tick size
                f = float(val)
                if f >= 1 or f == 0:
                    return int(f)
                # tick size → decimal places
                s = f"{f:.10f}".rstrip("0")
                if "." in s:
                    return len(s.split(".")[1])
                return 0
            except (TypeError, ValueError):
                return None

        return Market(
            exchange=self.exchange_id,
            symbol=str(symbol),
            base_asset=str(m.get("base") or ""),
            quote_asset=str(m.get("quote") or ""),
            active=m.get("active") if isinstance(m.get("active"), bool) else None,
            market_type=market_type,
            price_precision=_prec(precision.get("price")),
            amount_precision=_prec(precision.get("amount")),
            minimum_amount=optional_non_negative(amount_limits.get("min"), "minimum_amount"),
            minimum_cost=optional_non_negative(cost_limits.get("min"), "minimum_cost"),
            maker_fee=optional_non_negative(m.get("maker"), "maker_fee"),
            taker_fee=optional_non_negative(m.get("taker"), "taker_fee"),
        )

    def _normalize_balances(self, raw: dict[str, Any]) -> list[AssetBalance]:
        result: list[AssetBalance] = []
        # CCXT puts per-asset dicts under free/used/total keys and also nested
        free = raw.get("free") or {}
        used = raw.get("used") or {}
        total = raw.get("total") or {}
        assets = set(free) | set(used) | set(total)
        for asset in sorted(assets):
            if not asset or asset in ("info", "timestamp", "datetime", "free", "used", "total"):
                continue
            try:
                bal = AssetBalance(
                    asset=str(asset),
                    free=optional_non_negative(free.get(asset), f"{asset}.free"),
                    used=optional_non_negative(used.get(asset), f"{asset}.used"),
                    total=optional_non_negative(total.get(asset), f"{asset}.total"),
                )
            except MarketDataError:
                continue
            # Skip fully empty
            if (bal.free or 0) == 0 and (bal.used or 0) == 0 and (bal.total or 0) == 0:
                continue
            result.append(bal)
        return result

    def _normalize_ticker(self, symbol: str, raw: dict[str, Any]) -> Ticker:
        return Ticker(
            exchange=self.exchange_id,
            symbol=str(raw.get("symbol") or symbol),
            timestamp_ms=optional_timestamp_ms(raw.get("timestamp")),
            bid=optional_finite(raw.get("bid"), "bid"),
            ask=optional_finite(raw.get("ask"), "ask"),
            last=optional_finite(raw.get("last"), "last"),
            high=optional_finite(raw.get("high"), "high"),
            low=optional_finite(raw.get("low"), "low"),
            volume=optional_non_negative(raw.get("baseVolume"), "volume"),
            quote_volume=optional_non_negative(raw.get("quoteVolume"), "quote_volume"),
        )

    def _normalize_order_book(self, symbol: str, raw: dict[str, Any]) -> OrderBook:
        bids_raw = raw.get("bids") or []
        asks_raw = raw.get("asks") or []
        bids: list[OrderBookLevel] = []
        asks: list[OrderBookLevel] = []
        for level in bids_raw:
            if not level or len(level) < 2:
                continue
            price = require_positive(level[0], "bid.price")
            amount = require_non_negative(level[1], "bid.amount")
            bids.append(OrderBookLevel(price=price, amount=amount))
        for level in asks_raw:
            if not level or len(level) < 2:
                continue
            price = require_positive(level[0], "ask.price")
            amount = require_non_negative(level[1], "ask.amount")
            asks.append(OrderBookLevel(price=price, amount=amount))

        # Reject crossed book
        if bids and asks and bids[0].price > asks[0].price:
            raise MarketDataError(
                f"crossed order book for {symbol}: bid={bids[0].price} ask={asks[0].price}",
                exchange_id=self.exchange_id,
            )

        return OrderBook(
            exchange=self.exchange_id,
            symbol=symbol,
            timestamp_ms=optional_timestamp_ms(raw.get("timestamp")),
            bids=tuple(bids),
            asks=tuple(asks),
        )

    def _normalize_ohlcv(self, raw: list[Any]) -> list[OHLCVBar]:
        bars: list[OHLCVBar] = []
        for row in raw or []:
            if not row or len(row) < 6:
                continue
            ts = optional_timestamp_ms(row[0])
            if ts is None:
                raise MarketDataError("OHLCV bar missing timestamp")
            bars.append(
                OHLCVBar(
                    timestamp_ms=ts,
                    open=require_finite(row[1], "open"),
                    high=require_finite(row[2], "high"),
                    low=require_finite(row[3], "low"),
                    close=require_finite(row[4], "close"),
                    volume=require_non_negative(row[5], "volume"),
                )
            )
        return bars

    def _normalize_order(self, raw: dict[str, Any]) -> OpenOrder:
        return OpenOrder(
            exchange=self.exchange_id,
            id=str(raw.get("id") or ""),
            client_order_id=(str(raw["clientOrderId"]) if raw.get("clientOrderId") else None),
            symbol=str(raw.get("symbol") or ""),
            side=str(raw.get("side") or ""),
            order_type=str(raw.get("type") or ""),
            status=str(raw.get("status") or ""),
            price=optional_finite(raw.get("price"), "price"),
            amount=optional_non_negative(raw.get("amount"), "amount"),
            filled=optional_non_negative(raw.get("filled"), "filled"),
            remaining=optional_non_negative(raw.get("remaining"), "remaining"),
            timestamp_ms=optional_timestamp_ms(raw.get("timestamp")),
        )

    def _normalize_trade(self, raw: dict[str, Any]) -> Trade:
        fee = raw.get("fee") or {}
        return Trade(
            exchange=self.exchange_id,
            id=str(raw.get("id") or ""),
            order_id=str(raw["order"]) if raw.get("order") else None,
            symbol=str(raw.get("symbol") or ""),
            side=str(raw.get("side") or ""),
            price=require_finite(raw.get("price"), "price"),
            amount=require_non_negative(raw.get("amount"), "amount"),
            cost=optional_non_negative(raw.get("cost"), "cost"),
            fee_cost=optional_non_negative(fee.get("cost"), "fee.cost"),
            fee_currency=str(fee["currency"]) if fee.get("currency") else None,
            timestamp_ms=optional_timestamp_ms(raw.get("timestamp")),
        )

    def _normalize_position(self, raw: dict[str, Any]) -> Position:
        return Position(
            exchange=self.exchange_id,
            symbol=str(raw.get("symbol") or ""),
            side=str(raw["side"]) if raw.get("side") else None,
            size=optional_finite(raw.get("contracts") or raw.get("contractSize"), "size"),
            entry_price=optional_finite(raw.get("entryPrice"), "entry_price"),
            unrealized_pnl=optional_finite(raw.get("unrealizedPnl"), "unrealized_pnl"),
            leverage=optional_finite(raw.get("leverage"), "leverage"),
        )

    def _do_create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None,
        params: dict[str, object] | None,
    ) -> dict[str, object]:
        """Live CCXT order submission. Only called when trading_enabled."""
        self._ensure_connected()
        kwargs: dict[str, Any] = {}
        if params:
            kwargs.update(params)
        if price is not None:
            raw = self._safe_call(
                self._client.create_order,
                symbol,
                order_type,
                side,
                amount,
                price,
                kwargs if kwargs else None,
            )
        else:
            raw = self._safe_call(
                self._client.create_order,
                symbol,
                order_type,
                side,
                amount,
                None,
                kwargs if kwargs else None,
            )
        if not isinstance(raw, dict):
            return {"id": str(raw), "status": "unknown", "symbol": symbol}
        return dict(raw)

    def _do_cancel_order(self, order_id: str, symbol: str | None) -> dict[str, object]:
        self._ensure_connected()
        raw = self._safe_call(self._client.cancel_order, order_id, symbol)
        if not isinstance(raw, dict):
            return {"id": str(order_id), "status": "canceled"}
        return dict(raw)


def _sanitize_message(msg: str) -> str:
    """Best-effort removal of credential-looking substrings from error text."""
    # Redact long hex/base64-ish tokens that might be keys
    import re

    cleaned = re.sub(r"(?i)(api[_-]?key|secret|passphrase)\s*[:=]\s*\S+", r"\1=********", msg)
    cleaned = re.sub(r"\b[A-Za-z0-9]{32,}\b", "********", cleaned)
    return cleaned
