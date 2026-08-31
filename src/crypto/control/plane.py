"""Control plane — sole path from GUI/Telegram to trading authorities.

Never places orders directly. Never mutates RiskPolicy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from crypto.control.audit import ControlAuditLog
from crypto.control.auth import PinAuthConfig, PinAuthState
from crypto.execution.models import ExecutionMode
from crypto.risk.models import SafetyMode
from crypto.risk.policy import RiskPolicy


class CommandKind(Enum):
    PASSIVE = auto()  # saldo, portfolio, status
    CRITICAL = auto()  # cashout, emergency, mode change


class CommandResult(Enum):
    OK = auto()
    DENIED = auto()
    AUTH_REQUIRED = auto()
    LOCKED = auto()
    UNAVAILABLE = auto()
    INVALID = auto()


@dataclass(frozen=True, slots=True)
class ControlResponse:
    result: CommandResult
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppRuntimeState:
    """Mutable runtime flags controlled via control plane (not RiskPolicy)."""

    trading_mode: ExecutionMode = ExecutionMode.PAPER
    emergency_stop: bool = False
    safety_mode: SafetyMode = SafetyMode.NORMAL
    cashout_daily_limit: float = 0.0
    cashout_used_today: float = 0.0
    authorized_chat_ids: set[str] = field(default_factory=set)


class ControlPlane:
    """Mediates UI commands → Risk/Execution/Recovery. No exchange orders here."""

    PASSIVE_COMMANDS = frozenset(
        {
            "saldo",
            "portfolio",
            "positions",
            "orders",
            "ml_status",
            "opportunities",
            "system_health",
            "risk_status",
            "recovery_status",
            "settings_view",
        }
    )
    CRITICAL_COMMANDS = frozenset(
        {
            "emergency_stop",
            "cashout",
            "set_mode_live",
            "set_mode_paper",
            "settings_change",
        }
    )

    def __init__(
        self,
        *,
        pin_auth: PinAuthState | None = None,
        pin_config: PinAuthConfig | None = None,
        risk_policy: RiskPolicy | None = None,
        runtime: AppRuntimeState | None = None,
        mono_fn: Any = None,
    ) -> None:
        self.pin = pin_auth or PinAuthState()
        self.pin_config = pin_config or PinAuthConfig()
        self.risk_policy = risk_policy or RiskPolicy()
        self.runtime = runtime or AppRuntimeState()
        self.audit = ControlAuditLog()
        self._mono = mono_fn or time.monotonic
        # Snapshot providers (injected by host app)
        self._snapshot_fn: Any = None

    def set_snapshot_provider(self, fn: Any) -> None:
        self._snapshot_fn = fn

    def authorize_chat(self, chat_id: str) -> None:
        self.runtime.authorized_chat_ids.add(str(chat_id))
        self.audit.record("system", "authorize_chat", "ok", f"chat={chat_id}")

    def is_authorized_chat(self, chat_id: str) -> bool:
        return str(chat_id) in self.runtime.authorized_chat_ids

    def dispatch(
        self,
        command: str,
        *,
        actor: str,
        chat_id: str | None = None,
        pin: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> ControlResponse:
        cmd = command.strip().lower()
        params = params or {}

        if cmd not in self.PASSIVE_COMMANDS and cmd not in self.CRITICAL_COMMANDS:
            self.audit.record(actor, cmd, "invalid", "unknown command")
            return ControlResponse(CommandResult.INVALID, "unknown command")

        if chat_id is not None and not self.is_authorized_chat(chat_id):
            self.audit.record(actor, cmd, "denied", "unauthorized chat")
            return ControlResponse(CommandResult.DENIED, "unauthorized")

        if cmd in self.CRITICAL_COMMANDS:
            return self._dispatch_critical(cmd, actor=actor, pin=pin, params=params)

        return self._dispatch_passive(cmd, actor=actor)

    def _dispatch_passive(self, cmd: str, *, actor: str) -> ControlResponse:
        snap = self._collect_snapshot()
        self.audit.record(actor, cmd, "ok")
        return ControlResponse(CommandResult.OK, cmd, data=snap.get(cmd, snap))

    def _dispatch_critical(
        self,
        cmd: str,
        *,
        actor: str,
        pin: str | None,
        params: dict[str, Any],
    ) -> ControlResponse:
        now = self._mono()
        if self.pin.has_pin():
            if self.pin.session_valid(mono=now):
                pass  # session covers critical
            elif pin is None:
                self.audit.record(actor, cmd, "auth_required")
                return ControlResponse(
                    CommandResult.AUTH_REQUIRED, "PIN required for critical command"
                )
            elif not self.pin.verify(pin, mono=now, config=self.pin_config):
                if now < self.pin.locked_until_mono:
                    self.audit.record(actor, cmd, "locked")
                    return ControlResponse(CommandResult.LOCKED, "PIN locked out")
                self.audit.record(actor, cmd, "denied", "bad pin")
                return ControlResponse(CommandResult.DENIED, "invalid PIN")

        if cmd == "emergency_stop":
            return self._emergency_stop(actor)
        if cmd == "cashout":
            return self._cashout(actor, params)
        if cmd == "set_mode_live":
            self.runtime.trading_mode = ExecutionMode.LIVE
            self.audit.record(actor, cmd, "ok", "mode=LIVE")
            return ControlResponse(CommandResult.OK, "mode set to LIVE")
        if cmd == "set_mode_paper":
            self.runtime.trading_mode = ExecutionMode.PAPER
            self.audit.record(actor, cmd, "ok", "mode=PAPER")
            return ControlResponse(CommandResult.OK, "mode set to PAPER")
        if cmd == "settings_change":
            self.audit.record(actor, cmd, "ok")
            return ControlResponse(CommandResult.OK, "settings accepted")
        return ControlResponse(CommandResult.INVALID, "unknown critical")

    def _emergency_stop(self, actor: str) -> ControlResponse:
        self.runtime.emergency_stop = True
        self.runtime.safety_mode = SafetyMode.EMERGENCY_STOP
        # Does NOT mutate RiskPolicy fields
        self.audit.record(actor, "emergency_stop", "ok")
        return ControlResponse(
            CommandResult.OK,
            "EMERGENCY STOP active — new entries blocked",
            data={"safety_mode": self.runtime.safety_mode.name},
        )

    def _cashout(self, actor: str, params: dict[str, Any]) -> ControlResponse:
        amount = float(params.get("amount") or 0)
        if amount <= 0:
            self.audit.record(actor, "cashout", "invalid", "bad amount")
            return ControlResponse(CommandResult.INVALID, "invalid amount")
        available = float(params.get("available_balance") or 0)
        if amount > available:
            self.audit.record(actor, "cashout", "denied", "insufficient")
            return ControlResponse(CommandResult.DENIED, "insufficient balance")
        if (
            self.runtime.cashout_daily_limit > 0
            and self.runtime.cashout_used_today + amount > self.runtime.cashout_daily_limit
        ):
            self.audit.record(actor, "cashout", "denied", "daily limit")
            return ControlResponse(CommandResult.DENIED, "daily cashout limit")
        # Capability check — Phase 11 does not assume withdrawal API
        if not params.get("withdrawal_supported", False):
            self.audit.record(actor, "cashout", "unavailable")
            return ControlResponse(
                CommandResult.UNAVAILABLE,
                "WITHDRAWAL_REQUIRES_MANUAL_AUTHORIZATION",
            )
        if not params.get("confirmed", False):
            return ControlResponse(
                CommandResult.AUTH_REQUIRED,
                "confirmation required",
            )
        self.runtime.cashout_used_today += amount
        self.audit.record(actor, "cashout", "ok", f"amount={amount}")
        return ControlResponse(CommandResult.OK, "cashout submitted for verification")

    def _collect_snapshot(self) -> dict[str, Any]:
        if self._snapshot_fn is not None:
            return dict(self._snapshot_fn())
        return {
            "saldo": {"available": 0.0, "equity": 0.0},
            "portfolio": {},
            "risk_status": {
                "safety_mode": self.runtime.safety_mode.name,
                "emergency_stop": self.runtime.emergency_stop,
                "max_position_pct": self.risk_policy.max_position_pct,
            },
            "system_health": {},
            "trading_mode": self.runtime.trading_mode.name,
        }

    def risk_policy_fingerprint(self) -> tuple[float, float, float, int]:
        p = self.risk_policy
        return (
            p.max_position_pct,
            p.max_daily_loss_pct,
            p.max_drawdown_pct,
            p.max_concurrent_positions,
        )
