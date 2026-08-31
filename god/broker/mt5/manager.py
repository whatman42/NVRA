"""Production-grade MT5 Manager — external execution gateway orchestrator.

NVRAFX.exe never embeds terminal64.exe. This manager discovers, validates,
connects, heartbeats, and gates trading against an external MT5 terminal.

Fail-closed invariants:
- MT5 unhealthy → NO TRADE
- market data stale → NO TRADE
- account/server mismatch → NO TRADE
- symbol invalid → NO TRADE
- risk/policy/readiness fail → NO TRADE
- LIVE requires explicit LiveExecutionController arm + capital unlock
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from god.broker.models import AccountState, ProviderHealth
from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
from god.broker.mt5.errors import MT5NotAvailableError
from god.broker.mt5.heartbeat import HeartbeatMonitor, HeartbeatStatus
from god.broker.mt5.models import MT5AccountMode, MT5OrderRequest, MT5OrderResult, MT5Tick
from god.broker.mt5.reconnect import BackoffPolicy, ReconnectController
from god.mt5_runtime.detect import DetectionResult, detect_mt5
from god.mt5_runtime.states import MT5ConnectionState


@dataclass
class MT5ManagerHealth:
    ok: bool
    connected: bool
    account_mode: str
    terminal_found: bool
    terminal_path: Optional[str]
    heartbeat: dict[str, Any]
    market_data_fresh: bool
    last_error: str = ""
    reasons: list[str] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "connected": self.connected,
            "account_mode": self.account_mode,
            "terminal_found": self.terminal_found,
            "terminal_path": self.terminal_path,
            "heartbeat": self.heartbeat,
            "market_data_fresh": self.market_data_fresh,
            "last_error": self.last_error,
            "reasons": list(self.reasons),
            "snapshot": dict(self.snapshot),
        }


@dataclass
class MT5ManagerConfig:
    """Runtime config. Secrets via env only — never hardcode credentials."""

    connection: MT5ConnectionConfig = field(default_factory=MT5ConnectionConfig)
    expected_login: Optional[int] = None
    expected_server: Optional[str] = None
    expected_symbols: tuple[str, ...] = ("EURUSD",)
    max_tick_age_seconds: float = 30.0
    heartbeat_max_stale: float = 30.0
    require_demo_for_auto: bool = True


class MT5Manager:
    """
    Authoritative external MT5 gateway manager.

    Responsibilities:
    - discover & validate terminal
    - connect / reconnect / heartbeat
    - account & server identity checks
    - symbol validation + market-data freshness
    - order submission path (caller must still pass LiveExecutionController)
    - position/order reconciliation
    - graceful shutdown + crash-safe recovery hooks
    - structured audit
    """

    def __init__(
        self,
        config: Optional[MT5ManagerConfig] = None,
        *,
        adapter: Optional[MT5ExecutionAdapter] = None,
        mt5_module: Any = None,
    ) -> None:
        self.config = config or MT5ManagerConfig()
        if adapter is not None:
            self.adapter = adapter
        else:
            self.adapter = MT5ExecutionAdapter(
                self.config.connection,
                mt5_module=mt5_module,
            )
        self._detection: Optional[DetectionResult] = None
        self._last_tick: dict[str, MT5Tick] = {}
        self._last_tick_ts: dict[str, float] = {}
        self._audit: list[dict[str, Any]] = []
        self._started = False

    def _audit_event(self, kind: str, **payload: Any) -> None:
        self._audit.append({"ts": time.time(), "kind": kind, **payload})

    def discover(self) -> DetectionResult:
        self._detection = detect_mt5()
        self._audit_event(
            "discover",
            found=self._detection.found,
            paths=list(self._detection.paths),
        )
        return self._detection

    def validate_terminal(self) -> tuple[bool, str]:
        det = self._detection or self.discover()
        if not det.found:
            return False, "mt5_not_found"
        path = det.paths[0] if det.paths else None
        if path and self.config.connection.path is None:
            self.config.connection.path = path
            self.adapter.config.path = path
        return True, "ok"

    def connect(self) -> bool:
        self.validate_terminal()
        ok = self.adapter.connect()
        self._started = ok
        if ok:
            acct = self.adapter.account_state()
            if self.config.expected_login is not None:
                if str(acct.account_id) != str(self.config.expected_login):
                    self._audit_event("account_mismatch", expected=self.config.expected_login, got=acct.account_id)
                    self.adapter.disconnect()
                    self._started = False
                    return False
            if self.config.expected_server is not None:
                if (acct.server or "").lower() != self.config.expected_server.lower():
                    self._audit_event("server_mismatch", expected=self.config.expected_server, got=acct.server)
                    self.adapter.disconnect()
                    self._started = False
                    return False
            if self.config.require_demo_for_auto and self.adapter.account_mode() == MT5AccountMode.LIVE:
                if not self.config.connection.allow_live_account:
                    self._audit_event("live_blocked_at_manager")
                    self.adapter.disconnect()
                    self._started = False
                    return False
            self._audit_event("connected", mode=self.adapter.account_mode().value)
        else:
            self._audit_event("connect_fail", error=self.adapter.last_error)
        return ok

    def reconnect(self) -> bool:
        return self.adapter.connect_with_retry()

    def disconnect(self) -> None:
        self.adapter.disconnect()
        self._started = False
        self._audit_event("disconnected")

    def graceful_shutdown(self) -> dict[str, Any]:
        try:
            recon = self.adapter.reconcile()
        except Exception as e:
            recon = {"error": str(e)}
        self.disconnect()
        self._audit_event("graceful_shutdown")
        return {"ok": True, "reconcile": recon, "audit_events": len(self._audit)}

    def heartbeat(self) -> dict[str, Any]:
        return self.adapter.heartbeat()

    def symbol_tick(self, symbol: str) -> Optional[MT5Tick]:
        tick = self.adapter.symbol_tick(symbol)
        if tick is not None:
            self._last_tick[symbol] = tick
            self._last_tick_ts[symbol] = time.time()
        return tick

    def market_data_fresh(self, symbol: str) -> bool:
        ts = self._last_tick_ts.get(symbol)
        if ts is None:
            tick = self.symbol_tick(symbol)
            if tick is None:
                return False
            ts = self._last_tick_ts.get(symbol, 0)
        return (time.time() - ts) <= self.config.max_tick_age_seconds

    def validate_symbol(self, symbol: str) -> bool:
        if not self.adapter._connected:
            return False
        tick = self.symbol_tick(symbol)
        return tick is not None and tick.bid > 0 and tick.ask > 0

    def health(self) -> MT5ManagerHealth:
        reasons: list[str] = []
        det = self._detection or self.discover()
        connected = bool(self.adapter._connected)
        mode = self.adapter.account_mode().value
        hb = self.heartbeat()
        hb_ok = bool(hb.get("ok"))
        fresh = True
        for sym in self.config.expected_symbols:
            if connected and not self.market_data_fresh(sym):
                fresh = False
                reasons.append(f"stale_tick:{sym}")
        injected = self.adapter._mt5 is not None
        if not det.found and self.config.connection.path is None and not injected and not connected:
            reasons.append("terminal_not_found")
        if not connected:
            reasons.append("not_connected")
        if not hb_ok and connected:
            reasons.append("heartbeat_stale")
        if mode == "UNKNOWN" and connected:
            reasons.append("account_mode_unknown")
        if mode == "LIVE" and not self.config.connection.allow_live_account:
            reasons.append("live_account_not_allowed")
            connected = False

        ok = (
            connected
            and hb_ok
            and fresh
            and mode in ("DEMO", "CONTEST", "LIVE")
            and (mode != "LIVE" or self.config.connection.allow_live_account)
            and not reasons
        )
        if not ok and not reasons:
            reasons.append("unhealthy")

        acct = self.adapter.account_state()
        acct_dict = acct.to_dict() if hasattr(acct, "to_dict") else {}

        return MT5ManagerHealth(
            ok=ok,
            connected=connected,
            account_mode=mode,
            terminal_found=det.found,
            terminal_path=det.paths[0] if det.paths else self.config.connection.path,
            heartbeat=hb if isinstance(hb, dict) else {},
            market_data_fresh=fresh,
            last_error=self.adapter.last_error,
            reasons=reasons,
            snapshot={
                "provider_health": self.adapter.health().value,
                "account": acct_dict,
            },
        )

    def is_trade_allowed(self, symbol: str = "EURUSD") -> tuple[bool, str]:
        h = self.health()
        if not h.ok:
            return False, h.reasons[0] if h.reasons else "manager_unhealthy"
        if not self.validate_symbol(symbol):
            return False, "symbol_invalid"
        if not self.market_data_fresh(symbol):
            return False, "market_data_stale"
        if h.account_mode == "LIVE" and not self.config.connection.allow_live_account:
            return False, "live_not_allowed"
        if h.account_mode == "UNKNOWN":
            return False, "account_unknown"
        return True, "ok"

    def submit_order(self, request: MT5OrderRequest) -> MT5OrderResult:
        allowed, reason = self.is_trade_allowed(request.symbol)
        if not allowed:
            self._audit_event("order_blocked", reason=reason, client_order_id=request.client_order_id)
            return MT5OrderResult(ok=False, status="REJECTED", message=reason)
        return self.adapter.submit(request)

    def reconcile(self) -> dict[str, Any]:
        return self.adapter.reconcile()

    def open_positions(self) -> list[dict[str, Any]]:
        return self.adapter.open_positions()

    def account_state(self) -> AccountState:
        return self.adapter.account_state()

    def as_broker_submit(self):
        return self.adapter.as_broker_submit()

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit) + self.adapter.audit_log()

    def crash_recovery_snapshot(self) -> dict[str, Any]:
        return {
            "connected": bool(self.adapter._connected),
            "account_mode": self.adapter.account_mode().value,
            "positions": self.adapter.open_positions(),
            "orders": self.adapter.orders(),
            "client_order_ids": list(self.adapter._client_order_ids.keys()),
            "ts": time.time(),
        }
