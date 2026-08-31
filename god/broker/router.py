"""Broker mode router for CCXT exchanges and MT5.

This module is an authorization boundary. It never silently enables real trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from god.broker.modes import BrokerMode, BrokerModePolicy, policy_from_env
from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
from god.broker.models import AccountType
from crypto.core.credentials import CredentialStore
from crypto.exchanges.factory import create_exchange_adapter


@dataclass(frozen=True)
class BrokerSession:
    broker: str
    mode: BrokerMode
    sandbox: bool
    real_authorized: bool


class BrokerModeRouter:
    """Create a correctly gated broker session."""

    def policy(self, broker: str) -> BrokerModePolicy:
        return policy_from_env(broker)

    def create_crypto(self, broker: str, credentials: CredentialStore, account_id: str = "default") -> tuple[Any, BrokerSession]:
        policy = self.policy(broker)
        ok, reasons = policy.validate()
        if policy.mode is BrokerMode.REAL and not ok:
            raise PermissionError(f"REAL {broker} mode blocked: {', '.join(reasons)}")
        adapter = create_exchange_adapter(broker, credentials, account_id, sandbox=policy.sandbox)
        adapter.connect()
        adapter.enable_trading(policy.mode is BrokerMode.REAL)
        return adapter, BrokerSession(broker, policy.mode, policy.sandbox, policy.mode is BrokerMode.REAL)

    def create_mt5(self) -> tuple[MT5ExecutionAdapter, BrokerSession]:
        policy = self.policy("MT5")
        ok, reasons = policy.validate()
        if policy.mode is BrokerMode.REAL and not ok:
            raise PermissionError(f"REAL MT5 mode blocked: {', '.join(reasons)}")
        cfg = MT5ConnectionConfig.from_environment()
        cfg = MT5ConnectionConfig(**{**cfg.__dict__, "allow_live_account": policy.mode is BrokerMode.REAL})
        adapter = MT5ExecutionAdapter(cfg)
        if not adapter.connect():
            raise ConnectionError(adapter.last_error or "MT5 connection failed")
        account = adapter.account_state()
        if policy.mode is BrokerMode.DEMO and account.account_type is not AccountType.DEMO:
            adapter.disconnect()
            raise PermissionError("MT5 DEMO mode requires a DEMO account")
        if policy.mode is BrokerMode.REAL and account.account_type is not AccountType.LIVE:
            adapter.disconnect()
            raise PermissionError("MT5 REAL mode requires a LIVE account")
        return adapter, BrokerSession("MT5", policy.mode, policy.sandbox, policy.mode is BrokerMode.REAL)
