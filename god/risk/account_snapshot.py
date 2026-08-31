"""Account state snapshot for capital-adaptive risk.

Source of truth is live/provider account data — never a static config capital value.
Stale / invalid / inconsistent snapshots ⇒ NO TRADE.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from god.broker.models import AccountState, AccountType


@dataclass(frozen=True)
class AccountSnapshot:
    """Fresh account facts for risk calculation."""

    broker: str = ""
    account_id: str = ""
    server: str = ""
    account_type: str = "UNKNOWN"
    currency: str = "USD"
    balance: float = 0.0
    equity: float = 0.0
    free_margin: float = 0.0
    margin: float = 0.0
    leverage: float = 0.0
    margin_level: float = 0.0  # percent; 0 if no margin used
    open_positions: int = 0
    connected: bool = False
    observed_at: float = 0.0  # unix seconds
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "account_id": self.account_id,
            "server": self.server,
            "account_type": self.account_type,
            "currency": self.currency,
            "balance": self.balance,
            "equity": self.equity,
            "free_margin": self.free_margin,
            "margin": self.margin,
            "leverage": self.leverage,
            "margin_level": self.margin_level,
            "open_positions": self.open_positions,
            "connected": self.connected,
            "observed_at": self.observed_at,
            "source": self.source,
        }

    @classmethod
    def from_account_state(
        cls,
        state: AccountState,
        *,
        observed_at: Optional[float] = None,
        source: str = "provider",
        margin_level: float = 0.0,
    ) -> "AccountSnapshot":
        equity = float(state.equity if state.equity is not None else 0.0)
        balance = float(state.balance if state.balance is not None else equity)
        margin = float(state.margin if state.margin is not None else 0.0)
        free_margin = float(
            state.free_margin if state.free_margin is not None else max(0.0, equity - margin)
        )
        leverage = float(state.leverage if state.leverage is not None else 0.0)
        if margin_level <= 0 and margin > 0:
            margin_level = (equity / margin) * 100.0
        return cls(
            broker=state.broker or "",
            account_id=state.account_id or "",
            server=state.server or "",
            account_type=state.account_type.value
            if hasattr(state.account_type, "value")
            else str(state.account_type),
            currency=state.currency or "USD",
            balance=balance,
            equity=equity,
            free_margin=free_margin,
            margin=margin,
            leverage=leverage,
            margin_level=float(margin_level),
            open_positions=int(state.open_positions or 0),
            connected=bool(state.connected),
            observed_at=float(observed_at if observed_at is not None else time.time()),
            source=source,
        )


@dataclass
class AccountSnapshotPolicy:
    """Freshness and consistency gates for account data."""

    max_age_seconds: float = 30.0
    require_connected: bool = True
    require_positive_equity: bool = True
    max_equity_balance_divergence_pct: float = 0.50  # 50% relative guard


@dataclass(frozen=True)
class AccountValidation:
    ok: bool
    reasons: tuple[str, ...] = ()
    snapshot: Optional[AccountSnapshot] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
        }


class AccountStateEngine:
    """
    Validate and refresh account snapshots before every trade decision.

    Does NOT authorize LIVE. Does NOT size positions.
    """

    def __init__(self, policy: Optional[AccountSnapshotPolicy] = None) -> None:
        self.policy = policy or AccountSnapshotPolicy()
        self._last: Optional[AccountSnapshot] = None

    @property
    def last(self) -> Optional[AccountSnapshot]:
        return self._last

    def ingest(
        self,
        snapshot: AccountSnapshot,
        *,
        now: Optional[float] = None,
    ) -> AccountValidation:
        now = float(now if now is not None else time.time())
        reasons: list[str] = []
        if self.policy.require_connected and not snapshot.connected:
            reasons.append("not_connected")
        age = now - float(snapshot.observed_at or 0.0)
        if snapshot.observed_at <= 0:
            reasons.append("missing_timestamp")
        elif age > self.policy.max_age_seconds:
            reasons.append(f"stale_account:{age:.1f}s")
        if self.policy.require_positive_equity and snapshot.equity <= 0:
            reasons.append("non_positive_equity")
        if snapshot.balance < 0:
            reasons.append("negative_balance")
        if snapshot.free_margin < 0:
            reasons.append("negative_free_margin")
        if snapshot.equity > 0 and snapshot.balance > 0:
            rel = abs(snapshot.equity - snapshot.balance) / max(snapshot.balance, 1e-9)
            if rel > self.policy.max_equity_balance_divergence_pct and snapshot.margin <= 0:
                if snapshot.open_positions == 0:
                    reasons.append("equity_balance_inconsistent")
        if not snapshot.currency:
            reasons.append("missing_currency")
        if snapshot.account_type in ("", "UNKNOWN"):
            reasons.append("account_type_unknown")

        ok = len(reasons) == 0
        if ok:
            self._last = snapshot
        return AccountValidation(ok=ok, reasons=tuple(reasons), snapshot=snapshot)

    def from_provider_state(
        self,
        state: AccountState,
        *,
        now: Optional[float] = None,
        source: str = "provider",
        margin_level: float = 0.0,
    ) -> AccountValidation:
        snap = AccountSnapshot.from_account_state(
            state,
            observed_at=now,
            source=source,
            margin_level=margin_level,
        )
        return self.ingest(snap, now=now)
