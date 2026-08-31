"""LIVE capital gate — BLOCKED by default. Cannot be silently enabled."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Global invariant for TAHAP 8 acceptance: live capital remains blocked unless
# an explicit, audited unlock path is provided later. Default is always BLOCKED.
LIVE_CAPITAL_BLOCKED = True


@dataclass
class LiveCapitalGate:
    """Fail-closed gate for LIVE account execution.

    Paper and demo observation paths may proceed.
    LIVE order submission requires explicit unlock_token that is never shipped
    in default configuration.
    """

    blocked: bool = True
    unlock_reason: str = ""
    broker_orders_submitted: int = 0

    def allow_live_execution(self, *, unlock_token: Optional[str] = None) -> bool:
        if self.blocked or LIVE_CAPITAL_BLOCKED:
            return False
        if not unlock_token:
            return False
        # Placeholder: production would validate hardware-backed unlock.
        # Default distribution has no valid unlock tokens.
        return False

    def record_order_attempt(self, *, live: bool) -> None:
        if live:
            # Even attempts while blocked do not increment successful submissions
            return
        # paper path tracked elsewhere

    def assert_no_live_orders(self) -> None:
        if self.broker_orders_submitted != 0:
            raise RuntimeError("LIVE_ORDERS_NONZERO_VIOLATION")
