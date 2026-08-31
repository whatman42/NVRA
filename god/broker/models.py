"""Final Gate 2 — broker/account models. DETECTION ≠ AUTHORIZATION."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class AccountType(str, Enum):
    DEMO = "DEMO"
    LIVE = "LIVE"
    UNKNOWN = "UNKNOWN"


class LiveReadinessState(str, Enum):
    NOT_READY = "NOT_READY"
    DEMO_READY = "DEMO_READY"
    DEMO_VERIFIED = "DEMO_VERIFIED"
    LIVE_PREPARED = "LIVE_PREPARED"
    LIVE_VERIFICATION_REQUIRED = "LIVE_VERIFICATION_REQUIRED"
    LIVE_READY_FOR_CONTROLLED_TEST = "LIVE_READY_FOR_CONTROLLED_TEST"


class ProviderHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AccountState:
    broker: str = ""
    account_id: str = ""
    server: str = ""
    account_type: AccountType = AccountType.UNKNOWN
    currency: str = "USD"
    balance: Optional[float] = None
    equity: Optional[float] = None
    margin: Optional[float] = None
    free_margin: Optional[float] = None
    leverage: Optional[float] = None
    open_positions: int = 0
    connected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "account_id": self.account_id,
            "server": self.server,
            "account_type": self.account_type.value,
            "currency": self.currency,
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.margin,
            "free_margin": self.free_margin,
            "leverage": self.leverage,
            "open_positions": self.open_positions,
            "connected": self.connected,
        }
