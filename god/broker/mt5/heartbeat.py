"""Terminal heartbeat — fail if tick/account stale (bridge pattern)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class HeartbeatStatus:
    ok: bool
    age_seconds: float
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "age_seconds": self.age_seconds, "message": self.message}


class HeartbeatMonitor:
    def __init__(self, max_stale_seconds: float = 30.0) -> None:
        self.max_stale_seconds = max_stale_seconds
        self._last_ok_ts: float = 0.0

    def mark_ok(self) -> None:
        self._last_ok_ts = time.time()

    def check(self, *, now: Optional[float] = None) -> HeartbeatStatus:
        now = now if now is not None else time.time()
        if self._last_ok_ts <= 0:
            return HeartbeatStatus(ok=False, age_seconds=1e9, message="never_ok")
        age = now - self._last_ok_ts
        if age > self.max_stale_seconds:
            return HeartbeatStatus(ok=False, age_seconds=age, message="stale")
        return HeartbeatStatus(ok=True, age_seconds=age, message="ok")
