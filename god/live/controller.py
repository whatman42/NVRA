"""LIVE execution controller - arming, risk gate, kill switch, order path.

Default state: DISABLED.
LIVE requires: preflight PASS + explicit arm() + allow_live_account on adapter.
ML / recovery / hardware MUST NEVER arm LIVE.
AI MUST NEVER call order_send; only this controller may submit after gates.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from god.live.models import (
    HardRiskLimits,
    LiveExecutionState,
    LiveMode,
    LivePrerequisites,
    LiveValidationState,
    PreflightStatus,
)
from god.live.preflight import run_preflight
from god.live.authorization import LiveAuthorizationGate
from god.mt5_runtime.safety_gate import LiveCapitalGate, LIVE_CAPITAL_BLOCKED


@dataclass
class LiveOrderIntent:
    client_order_id: str
    symbol: str
    side: str
    size: float
    decision_id: str = ""
    risk_id: str = ""
    comment: str = "NVRA"


@dataclass
class LiveSubmitResult:
    ok: bool
    status: str
    reason: str = ""
    broker_response: Optional[dict[str, Any]] = None
    state: str = LiveExecutionState.DISABLED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reason": self.reason,
            "broker_response": self.broker_response,
            "state": self.state,
        }


class LiveExecutionController:
    """Authoritative LIVE gate + execution boundary."""

    def __init__(
        self,
        *,
        mode: LiveMode = LiveMode.DEMO,
        limits: Optional[HardRiskLimits] = None,
        capital_gate: Optional[LiveCapitalGate] = None,
    ) -> None:
        self.mode = mode
        self.limits = limits or HardRiskLimits()
        self.capital_gate = capital_gate or LiveCapitalGate(blocked=True)
        self.state = LiveExecutionState.DISABLED
        self._preflight_report = run_preflight(force_all_unknown=True)
        self._armed_at: float = 0.0
        self._halt_reason: str = ""
        self._client_order_ids: set[str] = set()
        self._audit: list[dict[str, Any]] = []
        self.broker_orders_submitted: int = 0
        self._open_positions: int = 0
        self._daily_loss: float = 0.0
        self._consecutive_losses: int = 0
        self.auth_gate = LiveAuthorizationGate(demo=(mode != LiveMode.LIVE))

    def _audit_event(self, kind: str, **payload: Any) -> None:
        self._audit.append({"ts": time.time(), "kind": kind, "state": self.state.value, **payload})

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "mode": self.mode.value,
            "preflight": self._preflight_report.to_dict(),
            "broker_orders_submitted": self.broker_orders_submitted,
            "live_capital_blocked": not self.capital_gate.allow_live_execution(),
            "halt_reason": self._halt_reason,
            "limits": self.limits.to_dict(),
            "validation_state": self.auth_gate.state.value,
            "can_submit_live": self.auth_gate.can_submit_live(),
        }

    def evaluate_preflight(self, checks: Optional[dict[str, PreflightStatus]] = None) -> dict[str, Any]:
        self._preflight_report = run_preflight(checks=checks)
        self._audit_event("preflight", overall=self._preflight_report.overall.value)
        if self._preflight_report.overall != PreflightStatus.PASS:
            if self.state not in (LiveExecutionState.HALTED, LiveExecutionState.BLOCKED):
                self.state = LiveExecutionState.BLOCKED
        return self._preflight_report.to_dict()

    def arm(self, *, operator_ack: str = "") -> dict[str, Any]:
        if self.state == LiveExecutionState.HALTED:
            return {"ok": False, "reason": "halted", "state": self.state.value}
        if self._preflight_report.overall != PreflightStatus.PASS:
            self.state = LiveExecutionState.BLOCKED
            self._audit_event("arm_denied", reason="preflight_not_pass")
            return {
                "ok": False,
                "reason": "preflight_not_pass",
                "preflight": self._preflight_report.to_dict(),
                "state": self.state.value,
            }
        if self.mode == LiveMode.LIVE and not self.capital_gate.allow_live_execution():
            self.state = LiveExecutionState.BLOCKED
            self._audit_event("arm_denied", reason="live_capital_blocked")
            return {
                "ok": False,
                "reason": "live_capital_blocked",
                "state": self.state.value,
            }
        if not operator_ack:
            self._audit_event("arm_denied", reason="missing_operator_ack")
            return {"ok": False, "reason": "missing_operator_ack", "state": self.state.value}

        if self.mode == LiveMode.LIVE:
            arm_res = self.auth_gate.arm(operator_authorization=operator_ack)
            if not arm_res.ok:
                self.state = LiveExecutionState.BLOCKED
                self._audit_event(
                    "arm_denied",
                    reason=arm_res.reason,
                    missing=list(arm_res.missing),
                )
                return {
                    "ok": False,
                    "reason": arm_res.reason,
                    "missing": list(arm_res.missing),
                    "validation_state": arm_res.state,
                    "state": self.state.value,
                }

        self.state = LiveExecutionState.ARMED
        self._armed_at = time.time()
        self._audit_event("armed", operator_ack=operator_ack[:64])
        return {
            "ok": True,
            "state": self.state.value,
            "armed_at": self._armed_at,
            "validation_state": self.auth_gate.state.value,
        }

    def arm_from_admin_policy(
        self,
        *,
        prerequisites_satisfied: bool,
        policy_reason: str = "admin_policy",
    ) -> dict[str, Any]:
        """Resume LIVE after restart from administrative autonomous policy."""
        if self.state == LiveExecutionState.HALTED:
            return {"ok": False, "reason": "halted", "state": self.state.value}
        if self._preflight_report.overall != PreflightStatus.PASS:
            self.state = LiveExecutionState.BLOCKED
            return {"ok": False, "reason": "preflight_not_pass", "state": self.state.value}
        if self.mode != LiveMode.LIVE:
            return {"ok": False, "reason": "not_live_mode", "state": self.state.value}
        if not self.capital_gate.allow_live_execution():
            self.state = LiveExecutionState.BLOCKED
            return {"ok": False, "reason": "live_capital_blocked", "state": self.state.value}
        arm_res = self.auth_gate.resume_from_admin_policy(
            autonomous_live=True,
            prerequisites_satisfied=prerequisites_satisfied,
        )
        if not arm_res.ok:
            self.state = LiveExecutionState.BLOCKED
            self._audit_event("arm_denied", reason=arm_res.reason, missing=list(arm_res.missing))
            return {
                "ok": False,
                "reason": arm_res.reason,
                "missing": list(arm_res.missing),
                "state": self.state.value,
            }
        self.state = LiveExecutionState.ARMED
        self._armed_at = time.time()
        self._audit_event("armed_from_admin_policy", reason=policy_reason[:64])
        return {
            "ok": True,
            "state": self.state.value,
            "armed_at": self._armed_at,
            "validation_state": self.auth_gate.state.value,
            "reason": "resumed_from_admin_policy",
        }

    def disarm(self) -> dict[str, Any]:
        if self.state == LiveExecutionState.HALTED:
            return {"ok": False, "reason": "halted", "state": self.state.value}
        self.state = LiveExecutionState.DISABLED
        self.auth_gate.disarm()
        self._audit_event("disarmed")
        return {
            "ok": True,
            "state": self.state.value,
            "validation_state": self.auth_gate.state.value,
        }

    def kill_switch(self, reason: str = "operator_kill") -> dict[str, Any]:
        self.state = LiveExecutionState.HALTED
        self._halt_reason = reason
        self._audit_event("kill_switch", reason=reason)
        return {"ok": True, "state": self.state.value, "reason": reason}

    def reset_after_halt(self, *, operator_ack: str = "") -> dict[str, Any]:
        if self.state != LiveExecutionState.HALTED:
            return {"ok": False, "reason": "not_halted", "state": self.state.value}
        if not operator_ack:
            return {"ok": False, "reason": "missing_operator_ack"}
        self.state = LiveExecutionState.DISABLED
        self._halt_reason = ""
        self._preflight_report = run_preflight(force_all_unknown=True)
        self._audit_event("reset_after_halt")
        return {"ok": True, "state": self.state.value}

    def _risk_check(self, intent: LiveOrderIntent) -> Optional[str]:
        if intent.size <= 0:
            return "invalid_size"
        if intent.size > self.limits.max_position_size:
            return "max_position_size"
        if self._open_positions >= self.limits.max_open_positions:
            return "max_open_positions"
        if self._daily_loss >= self.limits.max_daily_loss:
            return "max_daily_loss"
        if self._consecutive_losses >= self.limits.max_consecutive_losses:
            return "max_consecutive_losses"
        if not intent.symbol:
            return "invalid_symbol"
        if intent.side.upper() not in ("BUY", "SELL"):
            return "invalid_side"
        return None

    def submit_live_order(
        self,
        intent: LiveOrderIntent,
        *,
        broker_submit: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    ) -> LiveSubmitResult:
        if self.state == LiveExecutionState.HALTED:
            return LiveSubmitResult(
                ok=False, status="HALTED", reason=self._halt_reason or "halted", state=self.state.value
            )
        if self.state not in (LiveExecutionState.ARMED, LiveExecutionState.MONITORING):
            return LiveSubmitResult(
                ok=False, status="BLOCKED", reason=f"state_{self.state.value}", state=self.state.value
            )
        if self.mode == LiveMode.LIVE and not self.auth_gate.can_submit_live():
            return LiveSubmitResult(
                ok=False,
                status="BLOCKED",
                reason="live_not_authorized",
                state=self.state.value,
            )

        if intent.client_order_id in self._client_order_ids:
            self._audit_event("duplicate_blocked", client_order_id=intent.client_order_id)
            return LiveSubmitResult(
                ok=False,
                status="REJECTED",
                reason="duplicate_client_order_id",
                state=self.state.value,
            )

        risk_fail = self._risk_check(intent)
        if risk_fail:
            self._audit_event("risk_reject", reason=risk_fail)
            return LiveSubmitResult(
                ok=False, status="REJECTED", reason=risk_fail, state=self.state.value
            )

        if self.mode == LiveMode.LIVE:
            if not self.capital_gate.allow_live_execution():
                return LiveSubmitResult(
                    ok=False,
                    status="BLOCKED",
                    reason="live_capital_blocked",
                    state=self.state.value,
                )

        if broker_submit is None:
            return LiveSubmitResult(
                ok=False, status="REJECTED", reason="no_broker_submit", state=self.state.value
            )

        self.state = LiveExecutionState.EXECUTING
        req = {
            "client_order_id": intent.client_order_id,
            "symbol": intent.symbol,
            "side": intent.side.upper(),
            "size": float(intent.size),
            "decision_id": intent.decision_id,
            "risk_id": intent.risk_id,
            "comment": intent.comment,
        }
        try:
            resp = broker_submit(req)
        except Exception as e:
            self.state = LiveExecutionState.DEGRADED
            self._audit_event("broker_exception", error=str(e))
            return LiveSubmitResult(
                ok=False, status="REJECTED", reason=f"broker_exception:{e}", state=self.state.value
            )

        self._client_order_ids.add(intent.client_order_id)
        ok = bool(resp.get("ok")) if isinstance(resp, dict) else False
        status = str(resp.get("status", "UNKNOWN")) if isinstance(resp, dict) else "UNKNOWN"

        if ok:
            self.broker_orders_submitted += 1
            self._open_positions += 1
            self.state = LiveExecutionState.MONITORING
            self._audit_event("order_accepted", client_order_id=intent.client_order_id)
        else:
            self.state = LiveExecutionState.ARMED
            self._audit_event("order_rejected", client_order_id=intent.client_order_id, resp=resp)

        return LiveSubmitResult(
            ok=ok,
            status=status if ok else "REJECTED",
            reason="" if ok else str((resp or {}).get("message", "broker_rejected")),
            broker_response=resp if isinstance(resp, dict) else {"raw": str(resp)},
            state=self.state.value,
        )

    def record_fill_outcome(self, *, profit: float) -> None:
        if profit < 0:
            self._consecutive_losses += 1
            self._daily_loss += abs(profit)
        else:
            self._consecutive_losses = 0
        if self._open_positions > 0:
            self._open_positions -= 1

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)
