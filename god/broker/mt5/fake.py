"""Fake MetaTrader5 module for CI — DEMO by default, LIVE rejectable.

No real terminal required. Injectable into MT5ExecutionAdapter(mt5_module=...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# MT5-like constants (module-level for import convenience)
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
TRADE_ACTION_DEAL = 1
ORDER_TIME_GTC = 0
ORDER_FILLING_IOC = 1
TRADE_RETCODE_DONE = 10009
TIMEFRAME_H1 = 16385


@dataclass
class _AccountInfo:
    login: int = 1001
    server: str = "Fake-Demo"
    currency: str = "USD"
    balance: float = 10_000.0
    equity: float = 10_000.0
    margin: float = 0.0
    margin_free: float = 10_000.0
    leverage: int = 100
    trade_mode: int = 0  # 0=DEMO, 1=CONTEST, 2=LIVE


@dataclass
class _Tick:
    bid: float = 1.10000
    ask: float = 1.10020
    time: int = 1_700_000_000
    volume: float = 10.0


@dataclass
class _SymbolInfo:
    """Minimal symbol_info surface matching MetaTrader5.symbol_info()."""

    name: str = "EURUSD"
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    trade_contract_size: float = 100_000.0
    trade_tick_size: float = 0.00001
    trade_tick_value: float = 1.0
    margin_initial: float = 0.0
    trade_mode: int = 4  # SYMBOL_TRADE_MODE_FULL
    filling_mode: int = 1
    digits: int = 5
    point: float = 0.00001
    spread: int = 20
    trade_stops_level: int = 0


@dataclass
class _OrderResult:
    retcode: int = TRADE_RETCODE_DONE
    order: int = 5001
    deal: int = 6001
    volume: float = 0.01
    price: float = 1.10020
    comment: str = "fake"


@dataclass
class _Position:
    ticket: int
    symbol: str
    type: int
    volume: float
    price_open: float
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0


class FakeMetaTrader5:
    """Minimal MT5 API surface for unit tests.

    Exposes the same constant names as the real MetaTrader5 module so
    MT5ExecutionAdapter can use mt5.ORDER_TYPE_BUY etc. when this
    instance is injected as mt5_module. Values match official MT5 enums.
    """

    # --- constants matching MetaTrader5 module API ---
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    TIMEFRAME_H1 = 16385

    def __init__(
        self,
        *,
        trade_mode: int = 0,
        fail_initialize: bool = False,
        fail_order: bool = False,
    ) -> None:
        self._trade_mode = trade_mode
        self._fail_initialize = fail_initialize
        self._fail_order = fail_order
        self._connected = False
        self._positions: list[_Position] = []
        self._orders: list[Any] = []
        self._next_ticket = 7000
        self._last_error: tuple[int, str] = (0, "OK")
        self._account = _AccountInfo(trade_mode=trade_mode)
        self._tick = _Tick()
        self._symbols: dict[str, _SymbolInfo] = {
            "EURUSD": _SymbolInfo(name="EURUSD"),
            "GBPUSD": _SymbolInfo(name="GBPUSD"),
        }

    def initialize(self, **kwargs: Any) -> bool:
        if self._fail_initialize:
            self._last_error = (1, "init_fail")
            return False
        self._connected = True
        return True

    def shutdown(self) -> None:
        self._connected = False

    def last_error(self) -> tuple[int, str]:
        return self._last_error

    def terminal_info(self) -> Any:
        if not self._connected:
            return None
        return {"connected": True}

    def account_info(self) -> Optional[_AccountInfo]:
        if not self._connected:
            return None
        return self._account

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        return True

    def symbol_info_tick(self, symbol: str) -> Optional[_Tick]:
        if not self._connected:
            return None
        return self._tick

    def symbol_info(self, symbol: str) -> Optional[_SymbolInfo]:
        if not self._connected:
            return None
        return self._symbols.get(str(symbol).upper()) or self._symbols.get("EURUSD")

    def set_symbol_info(self, symbol: str, **kwargs: Any) -> None:
        """Test helper: override broker constraints for a symbol."""
        key = str(symbol).upper()
        base = self._symbols.get(key) or _SymbolInfo(name=key)
        data = {
            "name": key,
            "volume_min": float(kwargs.get("volume_min", base.volume_min)),
            "volume_max": float(kwargs.get("volume_max", base.volume_max)),
            "volume_step": float(kwargs.get("volume_step", base.volume_step)),
            "trade_contract_size": float(kwargs.get("trade_contract_size", base.trade_contract_size)),
            "trade_tick_size": float(kwargs.get("trade_tick_size", base.trade_tick_size)),
            "trade_tick_value": float(kwargs.get("trade_tick_value", base.trade_tick_value)),
            "margin_initial": float(kwargs.get("margin_initial", base.margin_initial)),
            "trade_mode": int(kwargs.get("trade_mode", base.trade_mode)),
            "filling_mode": int(kwargs.get("filling_mode", base.filling_mode)),
            "digits": int(kwargs.get("digits", base.digits)),
            "point": float(kwargs.get("point", base.point)),
            "spread": int(kwargs.get("spread", base.spread)),
            "trade_stops_level": int(kwargs.get("trade_stops_level", base.trade_stops_level)),
        }
        self._symbols[key] = _SymbolInfo(**data)

    def set_account_equity(self, equity: float, *, balance: Optional[float] = None) -> None:
        """Test helper: simulate deposit / withdrawal / PnL without restart."""
        eq = float(equity)
        bal = float(balance if balance is not None else equity)
        self._account.equity = eq
        self._account.balance = bal
        margin = float(getattr(self._account, "margin", 0.0) or 0.0)
        self._account.margin_free = max(0.0, eq - margin)

    def positions_get(self, ticket: Optional[int] = None, **kwargs: Any) -> list[_Position]:
        if ticket is not None:
            return [p for p in self._positions if p.ticket == ticket]
        return list(self._positions)

    def orders_get(self) -> list:
        return list(self._orders)

    def order_send(self, request: dict) -> Optional[_OrderResult]:
        if self._fail_order:
            self._last_error = (10004, "order_fail")
            return None
        if not self._connected:
            self._last_error = (1, "not_connected")
            return None
        if self._account.trade_mode == 2:
            self._last_error = (10017, "live_blocked_in_fake")
            return _OrderResult(retcode=10017, order=0, deal=0, volume=0, comment="live_blocked")

        vol = float(request.get("volume", 0.01))
        side = int(request.get("type", ORDER_TYPE_BUY))
        symbol = str(request.get("symbol", "EURUSD"))
        price = float(request.get("price", self._tick.ask if side == ORDER_TYPE_BUY else self._tick.bid))
        ticket = self._next_ticket
        self._next_ticket += 1

        if request.get("position"):
            pos_ticket = int(request["position"])
            self._positions = [p for p in self._positions if p.ticket != pos_ticket]
            return _OrderResult(retcode=TRADE_RETCODE_DONE, order=ticket, deal=ticket + 1000, volume=vol, price=price)

        self._positions.append(
            _Position(
                ticket=ticket,
                symbol=symbol,
                type=side,
                volume=vol,
                price_open=price,
                sl=float(request.get("sl") or 0),
                tp=float(request.get("tp") or 0),
            )
        )
        return _OrderResult(retcode=TRADE_RETCODE_DONE, order=ticket, deal=ticket + 1000, volume=vol, price=price)

    def copy_rates_from_pos(self, symbol: str, timeframe: int, start: int, count: int) -> list:
        base = 1.10
        out = []
        for i in range(count):
            c = base + i * 0.0001
            out.append((1_700_000_000 + i * 3600, c, c + 0.0002, c - 0.0002, c + 0.0001, 100))
        return out

    def set_trade_mode(self, mode: int) -> None:
        self._trade_mode = mode
        self._account.trade_mode = mode

    def set_tick(self, bid: float, ask: float) -> None:
        self._tick = _Tick(bid=bid, ask=ask)
