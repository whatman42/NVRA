"""ExchangeAdapter abstract interface.

Phase 2 is READ-ONLY. Order execution methods exist on the interface for
architectural continuity but must raise TradingDisabledError in all
production adapters until a later phase explicitly enables them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from crypto.exchanges.models import (
    AssetBalance,
    ConnectionHealth,
    Market,
    OHLCVBar,
    OpenOrder,
    OrderBook,
    PermissionReport,
    Position,
    Ticker,
    Trade,
)


class ExchangeAdapter(ABC):
    """Exchange-agnostic gateway.

    Implementations translate exchange-specific APIs into CRYPTO domain types.
    CCXT (or any other SDK) must not leak past this boundary.
    """

    @property
    @abstractmethod
    def exchange_id(self) -> str:
        """Stable identifier, e.g. 'binance', 'tokocrypto', 'indodax'."""

    @abstractmethod
    def connect(self) -> None:
        """Establish session / load markets. Idempotent where possible."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release resources. Safe to call multiple times."""

    @abstractmethod
    def health_check(self) -> ConnectionHealth:
        """Lightweight health probe. Must respect rate limits."""

    @abstractmethod
    def validate_permissions(self) -> PermissionReport:
        """Probe what the current API key can do (read-only checks only)."""

    @abstractmethod
    def fetch_markets(self) -> Sequence[Market]:
        """Return normalized market metadata."""

    @abstractmethod
    def fetch_balance(self) -> Sequence[AssetBalance]:
        """Return non-zero and zero balances the exchange reports."""

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> Ticker:
        """Latest ticker for symbol (exchange-native symbol format)."""

    @abstractmethod
    def fetch_order_book(self, symbol: str, limit: int | None = None) -> OrderBook:
        """Order book snapshot."""

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        since_ms: int | None = None,
        limit: int | None = None,
    ) -> Sequence[OHLCVBar]:
        """OHLCV candles. timeframe uses CCXT-style strings (1m, 5m, 1h, …)."""

    @abstractmethod
    def fetch_open_orders(self, symbol: str | None = None) -> Sequence[OpenOrder]:
        """Open orders (read-only)."""

    @abstractmethod
    def fetch_order(self, order_id: str, symbol: str | None = None) -> OpenOrder:
        """Single order by id (read-only)."""

    @abstractmethod
    def fetch_my_trades(
        self,
        symbol: str | None = None,
        since_ms: int | None = None,
        limit: int | None = None,
    ) -> Sequence[Trade]:
        """User trade history (read-only)."""

    @abstractmethod
    def fetch_positions(self) -> Sequence[Position]:
        """Open positions (spot exchanges typically return empty)."""

    # ------------------------------------------------------------------
    # Execution — gated; only ExecutionEngine may enable trading
    # ------------------------------------------------------------------

    _trading_enabled: bool = False

    def enable_trading(self, enabled: bool = True) -> None:
        """Allow or deny execution. REAL mode requires explicit authorization."""
        if enabled and not bool(getattr(self, "_sandbox", True)):
            import os
            authorized = (
                os.getenv("NVRA_REAL_TRADING_ENABLE", "0").lower() in {"1", "true", "yes"}
                and os.getenv("NVRA_REAL_TRADING_CONFIRM", "") == "I_UNDERSTAND_REAL_TRADING"
            )
            if not authorized:
                raise PermissionError(
                    "REAL trading requires NVRA_REAL_TRADING_ENABLE=true and "
                    "NVRA_REAL_TRADING_CONFIRM=I_UNDERSTAND_REAL_TRADING"
                )
        object.__setattr__(self, "_trading_enabled", bool(enabled))

    @property
    def trading_enabled(self) -> bool:
        return bool(getattr(self, "_trading_enabled", False))

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Submit an order. Raises TradingDisabledError unless trading is enabled.

        Only ExecutionEngine in LIVE mode should enable trading. Returns a
        normalized order dict from the exchange (or paper simulator).
        """
        from crypto.exchanges.errors import TradingDisabledError

        if not self.trading_enabled:
            raise TradingDisabledError(
                "Live trading is disabled. Only ExecutionEngine may enable it.",
                exchange_id=self.exchange_id,
            )
        return self._do_create_order(symbol, side, order_type, amount, price, params)

    def cancel_order(self, order_id: str, symbol: str | None = None) -> dict[str, object]:
        """Cancel an order. Raises TradingDisabledError unless trading is enabled."""
        from crypto.exchanges.errors import TradingDisabledError

        if not self.trading_enabled:
            raise TradingDisabledError(
                "Live trading is disabled. Only ExecutionEngine may enable it.",
                exchange_id=self.exchange_id,
            )
        return self._do_cancel_order(order_id, symbol)

    def _do_create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None,
        params: dict[str, object] | None,
    ) -> dict[str, object]:
        from crypto.exchanges.errors import UnsupportedCapabilityError

        raise UnsupportedCapabilityError(
            f"{self.exchange_id} adapter does not implement live create_order",
            exchange_id=self.exchange_id,
        )

    def _do_cancel_order(self, order_id: str, symbol: str | None) -> dict[str, object]:
        from crypto.exchanges.errors import UnsupportedCapabilityError

        raise UnsupportedCapabilityError(
            f"{self.exchange_id} adapter does not implement live cancel_order",
            exchange_id=self.exchange_id,
        )
