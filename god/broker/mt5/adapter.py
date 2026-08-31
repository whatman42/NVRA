"""MT5 execution adapter.

Thin, fail-closed wrapper around the external MetaTrader5 Python package.
The adapter is an execution gateway only: it does not generate signals and
cannot enable LIVE capital unless explicitly configured by the caller.
"""

from __future__ import annotations

import importlib
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from god.broker.models import AccountState, AccountType, ProviderHealth
from god.broker.mt5.errors import MT5IdempotencyError, MT5NotAvailableError
from god.broker.mt5.models import (
    MT5AccountMode,
    MT5OrderRequest,
    MT5OrderResult,
    MT5Tick,
)
from god.risk.broker_constraints import (
    ConstraintsValidation,
    constraints_from_dict,
)


@dataclass
class MT5ConnectionConfig:
    """External terminal connection configuration.

    Credentials are read from environment variables and are never persisted
    by this adapter. ``allow_live_account`` is deliberately False by default.
    """

    path: Optional[str] = None
    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None
    timeout_ms: int = 10_000
    portable: bool = False
    allow_live_account: bool = False

    @classmethod
    def from_environment(cls) -> "MT5ConnectionConfig":
        login_raw = os.getenv("NVRAFX_MT5_LOGIN") or os.getenv("MT5_LOGIN")
        try:
            login = int(login_raw) if login_raw else None
        except ValueError:
            login = None
        return cls(
            path=os.getenv("NVRAFX_MT5_PATH") or os.getenv("MT5_PATH"),
            login=login,
            password=os.getenv("NVRAFX_MT5_PASSWORD") or os.getenv("MT5_PASSWORD"),
            server=os.getenv("NVRAFX_MT5_SERVER") or os.getenv("MT5_SERVER"),
            timeout_ms=int(os.getenv("NVRAFX_MT5_TIMEOUT_MS", "10000")),
            portable=os.getenv("NVRAFX_MT5_PORTABLE", "0").lower() in ("1", "true", "yes"),
            allow_live_account=os.getenv("NVRAFX_ALLOW_LIVE_ACCOUNT", "0").lower()
            in ("1", "true", "yes"),
        )


class MT5ExecutionAdapter:
    """Authoritative broker gateway with idempotent order submission."""

    def __init__(self, config: Optional[MT5ConnectionConfig] = None, *, mt5_module: Any = None):
        self.config = config or MT5ConnectionConfig.from_environment()
        self._mt5 = mt5_module
        self._connected = False
        self._last_error = ""
        self._last_tick: dict[str, MT5Tick] = {}
        self._last_tick_ts: dict[str, float] = {}
        self._client_order_ids: dict[str, MT5OrderResult] = {}
        self._audit: list[dict[str, Any]] = []
        self._last_account_mode = MT5AccountMode.UNKNOWN

    @property
    def last_error(self) -> str:
        return self._last_error

    def _set_error(self, message: str) -> None:
        self._last_error = str(message)

    def _load_module(self) -> Any:
        if self._mt5 is not None:
            return self._mt5
        try:
            self._mt5 = importlib.import_module("MetaTrader5")
        except Exception as exc:
            raise MT5NotAvailableError(f"MetaTrader5 unavailable: {exc}") from exc
        return self._mt5

    def _audit_event(self, kind: str, **payload: Any) -> None:
        self._audit.append({"ts": time.time(), "kind": kind, **payload})

    def connect(self) -> bool:
        try:
            mt5 = self._load_module()
            kwargs: dict[str, Any] = {}
            if self.config.path:
                kwargs["path"] = self.config.path
            if self.config.login is not None:
                kwargs["login"] = self.config.login
            if self.config.password:
                kwargs["password"] = self.config.password
            if self.config.server:
                kwargs["server"] = self.config.server
            if self.config.timeout_ms:
                kwargs["timeout"] = self.config.timeout_ms
            if self.config.portable:
                kwargs["portable"] = True

            ok = bool(mt5.initialize(**kwargs))
            if not ok:
                err = mt5.last_error() if hasattr(mt5, "last_error") else "initialize_failed"
                self._set_error(f"initialize_failed:{err}")
                self._connected = False
                self._audit_event("connect_failed", error=self._last_error)
                return False

            self._connected = True
            self._set_error("")
            mode = self.account_mode()
            if mode == MT5AccountMode.LIVE and not self.config.allow_live_account:
                self._set_error("live_account_blocked")
                self._audit_event("live_account_blocked")
                self.disconnect()
                return False
            self._audit_event("connected", account_mode=mode.value)
            return True
        except MT5NotAvailableError as exc:
            self._set_error(str(exc))
            self._connected = False
            return False
        except Exception as exc:
            self._set_error(f"connect_exception:{exc}")
            self._connected = False
            self._audit_event("connect_exception", error=self._last_error)
            return False

    def connect_with_retry(self, attempts: int = 3, delay_seconds: float = 1.0) -> bool:
        for attempt in range(max(1, int(attempts))):
            if self.connect():
                return True
            if attempt + 1 < attempts:
                time.sleep(max(0.0, delay_seconds))
        return False

    def disconnect(self) -> None:
        try:
            if self._mt5 is not None and self._connected:
                self._mt5.shutdown()
        finally:
            self._connected = False
            self._audit_event("disconnected")

    def account_mode(self) -> MT5AccountMode:
        if not self._connected:
            return MT5AccountMode.UNKNOWN
        try:
            info = self._mt5.account_info()
            if info is None:
                return MT5AccountMode.UNKNOWN
            mode = int(getattr(info, "trade_mode", -1))
            result = {
                0: MT5AccountMode.DEMO,
                1: MT5AccountMode.CONTEST,
                2: MT5AccountMode.LIVE,
            }.get(mode, MT5AccountMode.UNKNOWN)
            self._last_account_mode = result
            return result
        except Exception:
            return MT5AccountMode.UNKNOWN

    def health(self) -> ProviderHealth:
        if not self._connected or self._mt5 is None:
            return ProviderHealth.UNAVAILABLE
        try:
            terminal = self._mt5.terminal_info()
            account = self._mt5.account_info()
            if terminal is None or account is None:
                return ProviderHealth.DEGRADED
            if self.account_mode() == MT5AccountMode.LIVE and not self.config.allow_live_account:
                return ProviderHealth.DEGRADED
            return ProviderHealth.HEALTHY
        except Exception:
            return ProviderHealth.DEGRADED

    def heartbeat(self) -> dict[str, Any]:
        healthy = self.health() == ProviderHealth.HEALTHY
        return {
            "ok": healthy,
            "connected": self._connected,
            "account_mode": self.account_mode().value,
            "ts": time.time(),
            "last_error": self._last_error,
        }

    def account_state(self) -> AccountState:
        if not self._connected or self._mt5 is None:
            return AccountState(connected=False)
        try:
            info = self._mt5.account_info()
            if info is None:
                return AccountState(connected=False)
            mode = self.account_mode()
            account_type = (
                AccountType.DEMO if mode == MT5AccountMode.DEMO
                else AccountType.LIVE if mode == MT5AccountMode.LIVE
                else AccountType.UNKNOWN
            )
            positions = self.open_positions()
            return AccountState(
                broker="MetaTrader5",
                account_id=str(getattr(info, "login", "")),
                server=str(getattr(info, "server", "")),
                account_type=account_type,
                currency=str(getattr(info, "currency", "USD")),
                balance=float(getattr(info, "balance", 0.0)),
                equity=float(getattr(info, "equity", 0.0)),
                margin=float(getattr(info, "margin", 0.0)),
                free_margin=float(getattr(info, "margin_free", 0.0)),
                leverage=float(getattr(info, "leverage", 0.0)),
                open_positions=len(positions),
                connected=True,
            )
        except Exception as exc:
            self._set_error(f"account_state:{exc}")
            return AccountState(connected=False)

    def symbol_tick(self, symbol: str) -> Optional[MT5Tick]:
        if not self._connected or self._mt5 is None:
            return None
        try:
            symbol = str(symbol).upper()
            if hasattr(self._mt5, "symbol_select"):
                if not self._mt5.symbol_select(symbol, True):
                    return None
            tick = self._mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            result = MT5Tick(
                symbol=symbol,
                bid=float(getattr(tick, "bid", 0.0)),
                ask=float(getattr(tick, "ask", 0.0)),
                time=int(getattr(tick, "time", 0)),
                volume=float(getattr(tick, "volume", 0.0)),
            )
            if result.bid <= 0 or result.ask <= 0 or result.ask < result.bid:
                return None
            self._last_tick[symbol] = result
            self._last_tick_ts[symbol] = time.time()
            return result
        except Exception as exc:
            self._set_error(f"symbol_tick:{exc}")
            return None

    def symbol_constraints(self, symbol: str) -> ConstraintsValidation:
        if not self._connected or self._mt5 is None:
            return ConstraintsValidation(False, ("not_connected",), None)
        try:
            info = self._mt5.symbol_info(str(symbol).upper())
            if info is None:
                return ConstraintsValidation(False, ("symbol_not_found",), None)
            mode_map = {0: "DISABLED", 1: "CLOSE_ONLY", 4: "FULL"}
            fill_map = {0: "FOK", 1: "IOC", 2: "RETURN"}
            data = {
                "volume_min": getattr(info, "volume_min", None),
                "volume_max": getattr(info, "volume_max", None),
                "volume_step": getattr(info, "volume_step", None),
                "contract_size": getattr(info, "trade_contract_size", None),
                "tick_size": getattr(info, "trade_tick_size", None),
                "tick_value": getattr(info, "trade_tick_value", None),
                "margin_initial": getattr(info, "margin_initial", 0.0),
                "trade_mode": mode_map.get(int(getattr(info, "trade_mode", 4)), "UNKNOWN"),
                "filling_mode": fill_map.get(int(getattr(info, "filling_mode", 1)), "UNKNOWN"),
                "digits": getattr(info, "digits", 5),
                "point": getattr(info, "point", None),
                "spread_points": getattr(info, "spread", 0),
                "stops_level": getattr(info, "trade_stops_level", 0),
            }
            return constraints_from_dict(str(symbol).upper(), data)
        except Exception as exc:
            return ConstraintsValidation(False, (f"constraints_error:{exc}",), None)

    def _position_dict(self, p: Any) -> dict[str, Any]:
        return {
            "ticket": int(getattr(p, "ticket", 0)),
            "symbol": str(getattr(p, "symbol", "")),
            "type": int(getattr(p, "type", -1)),
            "volume": float(getattr(p, "volume", 0.0)),
            "price_open": float(getattr(p, "price_open", 0.0)),
            "sl": float(getattr(p, "sl", 0.0)),
            "tp": float(getattr(p, "tp", 0.0)),
            "profit": float(getattr(p, "profit", 0.0)),
        }

    def open_positions(self) -> list[dict[str, Any]]:
        if not self._connected or self._mt5 is None:
            return []
        try:
            positions = self._mt5.positions_get()
            return [self._position_dict(p) for p in (positions or [])]
        except Exception as exc:
            self._set_error(f"positions:{exc}")
            return []

    def orders(self) -> list[dict[str, Any]]:
        if not self._connected or self._mt5 is None:
            return []
        try:
            orders = self._mt5.orders_get()
            return [dict(vars(o)) if hasattr(o, "__dict__") else {"value": str(o)} for o in (orders or [])]
        except Exception as exc:
            self._set_error(f"orders:{exc}")
            return []

    def _retcode(self, result: Any) -> int:
        return int(getattr(result, "retcode", -1))

    def submit(self, request: MT5OrderRequest) -> MT5OrderResult:
        if not self._connected:
            return MT5OrderResult(False, "REJECTED", message="not_connected")
        if not request.client_order_id:
            return MT5OrderResult(False, "REJECTED", message="missing_client_order_id")
        if request.client_order_id in self._client_order_ids:
            raise MT5IdempotencyError(f"duplicate_client_order_id:{request.client_order_id}")
        mode = self.account_mode()
        if mode == MT5AccountMode.LIVE and not self.config.allow_live_account:
            return MT5OrderResult(False, "REJECTED", message="live_account_blocked")
        if mode not in (MT5AccountMode.DEMO, MT5AccountMode.CONTEST, MT5AccountMode.LIVE):
            return MT5OrderResult(False, "REJECTED", message="account_mode_unknown")
        if request.volume <= 0:
            return MT5OrderResult(False, "REJECTED", message="invalid_volume")

        tick = self.symbol_tick(request.symbol)
        if tick is None:
            return MT5OrderResult(False, "REJECTED", message="symbol_tick_unavailable")

        side = request.side.upper()
        if side not in ("BUY", "SELL"):
            return MT5OrderResult(False, "REJECTED", message="invalid_side")

        mt5 = self._mt5
        order_type = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
        price = request.price if request.price is not None else (
            tick.ask if side == "BUY" else tick.bid
        )
        filling = getattr(mt5, "ORDER_FILLING_IOC", 1)
        payload = {
            "action": getattr(mt5, "TRADE_ACTION_DEAL", 1),
            "symbol": request.symbol,
            "volume": float(request.volume),
            "type": order_type,
            "price": float(price),
            "sl": float(request.sl or 0.0),
            "tp": float(request.tp or 0.0),
            "deviation": 20,
            "magic": 260826,
            "comment": request.comment[:31],
            "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
            "type_filling": filling,
        }

        try:
            raw = mt5.order_send(payload)
        except Exception as exc:
            result = MT5OrderResult(False, "UNKNOWN", message=f"order_send_exception:{exc}")
            self._client_order_ids[request.client_order_id] = result
            self._audit_event("order_unknown", request=request.to_audit(), message=result.message)
            return result

        if raw is None:
            err = mt5.last_error() if hasattr(mt5, "last_error") else "order_send_none"
            result = MT5OrderResult(False, "UNKNOWN", message=str(err))
            self._client_order_ids[request.client_order_id] = result
            self._audit_event("order_unknown", request=request.to_audit(), message=result.message)
            return result

        retcode = self._retcode(raw)
        done = int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))
        ok = retcode == done
        result = MT5OrderResult(
            ok=ok,
            status="FILLED" if ok else "REJECTED",
            broker_order_id=str(getattr(raw, "order", "")) if getattr(raw, "order", 0) else None,
            deal_id=str(getattr(raw, "deal", "")) if getattr(raw, "deal", 0) else None,
            filled_volume=float(getattr(raw, "volume", 0.0)),
            price=float(getattr(raw, "price", price)),
            message="ok" if ok else f"broker_retcode:{retcode}",
            raw={"retcode": retcode},
        )
        self._client_order_ids[request.client_order_id] = result
        self._audit_event("order_result", request=request.to_audit(), result=result.to_dict())
        return result

    def reconcile(self) -> dict[str, Any]:
        positions = self.open_positions()
        orders = self.orders()
        return {
            "ok": self._connected and self.health() == ProviderHealth.HEALTHY,
            "mode": self.account_mode().value,
            "positions": positions,
            "orders": orders,
            "client_order_ids": list(self._client_order_ids.keys()),
            "ts": time.time(),
        }

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)

    def as_broker_submit(self) -> Callable[[Any], Any]:
        return self.submit
