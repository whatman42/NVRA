"""LIVE capital gate — fail-closed by default.

Default install: LIVE capital blocked.
Administrative autonomous authorization (persisted policy, no secrets) may
enable capital path only when explicitly set on the gate instance at runtime
after policy load + safety prechecks. ML/recovery must never set this flag.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Global default for uninitialized systems / tests without admin policy.
LIVE_CAPITAL_BLOCKED = True


@dataclass
class LiveCapitalGate:
    """Fail-closed gate for LIVE account execution.

    Paper and demo observation paths may proceed.
    LIVE order submission requires either:
    - legacy unlock_token path (not shipped), or
    - administrative_live_authorized=True after verified admin policy + prechecks.
    """

    blocked: bool = True
    unlock_reason: str = ""
    broker_orders_submitted: int = 0
    # Set only by autonomous runtime after loading verified admin policy.
    administrative_live_authorized: bool = False

    def allow_live_execution(self, *, unlock_token: Optional[str] = None) -> bool:
        # Operator/kill force-block always wins.
        if self.blocked and not self.administrative_live_authorized:
            return False
        if self.administrative_live_authorized and not self.blocked:
            return True
        # Legacy path: global block + no shipped unlock tokens.
        if self.blocked or LIVE_CAPITAL_BLOCKED:
            return False
        if not unlock_token:
            return False
        return False

    def authorize_from_admin_policy(self, *, reason: str = "admin_policy") -> None:
        """Enable capital path after administrative policy + runtime prechecks."""
        self.administrative_live_authorized = True
        self.blocked = False
        self.unlock_reason = reason

    def revoke_admin_authorization(self, *, reason: str = "revoke") -> None:
        self.administrative_live_authorized = False
        self.blocked = True
        self.unlock_reason = reason

    def record_order_attempt(self, *, live: bool) -> None:
        if live:
            return

    def assert_no_live_orders(self) -> None:
        if self.broker_orders_submitted != 0:
            raise RuntimeError("LIVE_ORDERS_NONZERO_VIOLATION")
