"""Typed MT5 connection and account states."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MT5ConnectionState(str, Enum):
    MT5_NOT_FOUND = "MT5_NOT_FOUND"
    MT5_DISCONNECTED = "MT5_DISCONNECTED"
    MT5_CONNECTING = "MT5_CONNECTING"
    MT5_CONNECTED = "MT5_CONNECTED"
    BRIDGE_VERSION_MISMATCH = "BRIDGE_VERSION_MISMATCH"
    BRIDGE_HANDSHAKE_FAILED = "BRIDGE_HANDSHAKE_FAILED"
    BRIDGE_ERROR = "BRIDGE_ERROR"
    RECONCILING = "RECONCILING"


class AccountMode(str, Enum):
    UNKNOWN = "UNKNOWN"
    DEMO = "DEMO"
    LIVE = "LIVE"


@dataclass
class TerminalSnapshot:
    state: MT5ConnectionState
    account_mode: AccountMode = AccountMode.UNKNOWN
    account_id: Optional[str] = None
    server: Optional[str] = None
    balance: Optional[float] = None
    equity: Optional[float] = None
    margin: Optional[float] = None
    free_margin: Optional[float] = None
    positions: List[Dict[str, Any]] = field(default_factory=list)
    orders: List[Dict[str, Any]] = field(default_factory=list)
    terminal_path: Optional[str] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "account_mode": self.account_mode.value,
            "account_id": self.account_id,
            "server": self.server,
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.margin,
            "free_margin": self.free_margin,
            "positions": list(self.positions),
            "orders": list(self.orders),
            "terminal_path": self.terminal_path,
            "message": self.message,
        }
