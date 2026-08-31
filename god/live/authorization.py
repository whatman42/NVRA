"""LIVE authorization / validation gate — fail-closed.

Does not implement strategy, risk math, or broker order algorithms.
Only answers: may LIVE be ARMED given explicit operator intent + prerequisites?

Default: LIVE_DISABLED (or DEMO when product mode is DEMO).
Exceptions never open LIVE. No credentials/secrets are stored or logged here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from god.live.models import LivePrerequisites, LiveValidationState


@dataclass
class LiveArmResult:
    ok: bool
    state: str
    reason: str = ""
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "state": self.state,
            "reason": self.reason,
            "missing": list(self.missing),
        }


class LiveAuthorizationGate:
    """Product-facing LIVE validation state machine (fail-closed).

    Invariants:
    - starts LIVE_DISABLED unless constructed for DEMO
    - no automatic transition to LIVE_ARMED
    - SAFE_MODE blocks arm and can_submit_live
    - operator_authorization is never logged (caller must not pass secrets)
    """

    def __init__(
        self,
        *,
        demo: bool = False,
        prerequisites: Optional[LivePrerequisites] = None,
    ) -> None:
        self._prereq = prerequisites or LivePrerequisites()
        self._explicit_armed: bool = False
        self._safe_mode: bool = False
        self._safe_reason: str = ""
        self._state = LiveValidationState.DEMO if demo else LiveValidationState.LIVE_DISABLED

    @property
    def state(self) -> LiveValidationState:
        return self._state

    @property
    def prerequisites(self) -> LivePrerequisites:
        return self._prereq

    def status(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "safe_mode": self._safe_mode,
            "safe_reason": self._safe_reason,
            "explicit_armed": self._explicit_armed,
            "prerequisites": self._prereq.as_dict(),
            "missing": self._prereq.missing(),
            "can_submit_live": self.can_submit_live(),
        }

    def update_prerequisites(self, **flags: bool) -> LiveValidationState:
        for key, value in flags.items():
            if hasattr(self._prereq, key) and isinstance(value, bool):
                setattr(self._prereq, key, value)
        return self.recompute()

    def set_prerequisites(self, prereq: LivePrerequisites) -> LiveValidationState:
        self._prereq = prereq
        return self.recompute()

    def recompute(self) -> LiveValidationState:
        if self._safe_mode:
            self._state = LiveValidationState.SAFE_MODE
            self._explicit_armed = False
            return self._state
        if self._state == LiveValidationState.DEMO:
            return self._state
        if self._explicit_armed and self._prereq.all_satisfied():
            self._state = LiveValidationState.LIVE_ARMED
            return self._state
        self._explicit_armed = False
        if self._prereq.all_satisfied():
            self._state = LiveValidationState.LIVE_READY
        else:
            self._state = LiveValidationState.LIVE_DISABLED
        return self._state

    def enter_safe_mode(self, reason: str = "fault") -> LiveValidationState:
        self._safe_mode = True
        self._safe_reason = reason or "fault"
        self._explicit_armed = False
        self._state = LiveValidationState.SAFE_MODE
        return self._state

    def exit_safe_mode(self) -> LiveValidationState:
        self._safe_mode = False
        self._safe_reason = ""
        self._explicit_armed = False
        if self._state == LiveValidationState.DEMO:
            return self._state
        return self.recompute()

    def arm(self, *, operator_authorization: str = "") -> LiveArmResult:
        if self._state == LiveValidationState.DEMO:
            return LiveArmResult(
                ok=False, state=self._state.value, reason="demo_mode_no_live_arm"
            )
        if self._safe_mode or self._state == LiveValidationState.SAFE_MODE:
            return LiveArmResult(
                ok=False,
                state=LiveValidationState.SAFE_MODE.value,
                reason="safe_mode",
                missing=self._prereq.missing(),
            )
        if not operator_authorization or not str(operator_authorization).strip():
            self._explicit_armed = False
            self.recompute()
            return LiveArmResult(
                ok=False,
                state=self._state.value,
                reason="missing_operator_authorization",
                missing=self._prereq.missing(),
            )
        missing = self._prereq.missing()
        if missing:
            self._explicit_armed = False
            self.recompute()
            return LiveArmResult(
                ok=False,
                state=self._state.value,
                reason="prerequisites_unmet",
                missing=missing,
            )
        self._explicit_armed = True
        self._state = LiveValidationState.LIVE_ARMED
        return LiveArmResult(ok=True, state=self._state.value, reason="armed")

    def disarm(self) -> LiveArmResult:
        self._explicit_armed = False
        if self._safe_mode:
            self._state = LiveValidationState.SAFE_MODE
            return LiveArmResult(ok=True, state=self._state.value, reason="disarmed_in_safe_mode")
        if self._state == LiveValidationState.DEMO:
            return LiveArmResult(ok=True, state=self._state.value, reason="demo")
        self.recompute()
        return LiveArmResult(ok=True, state=self._state.value, reason="disarmed")

    def can_submit_live(self) -> bool:
        return (
            self._state == LiveValidationState.LIVE_ARMED
            and not self._safe_mode
            and self._explicit_armed
            and self._prereq.all_satisfied()
        )

    def note_gui_fault(self) -> None:
        """GUI crash must not arm or unlock LIVE."""
        return None
