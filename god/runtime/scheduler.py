"""Scheduler for N.U.N.G. — no busy-loop, externally driven."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from .clock import Clock, SystemClock
from .models import RuntimeConfig


class Scheduler:
    """Interval-based next-trigger calculation. No daemon threads."""

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.clock = clock or SystemClock()
        self._last_run_iso: Optional[str] = None

    def should_run(self, *, force: bool = False) -> bool:
        if force:
            return True
        if self._last_run_iso is None:
            return True
        now = self.clock.now()
        try:
            last_s = self._last_run_iso.replace("Z", "+00:00")
            from datetime import datetime

            last = datetime.fromisoformat(last_s)
            if last.tzinfo is None:
                from datetime import timezone

                last = last.replace(tzinfo=timezone.utc)
            return (now - last).total_seconds() >= self.config.interval_seconds
        except Exception:
            return True

    def wait_duration(self) -> float:
        if self._last_run_iso is None:
            return 0.0
        try:
            from datetime import datetime, timezone

            last_s = self._last_run_iso.replace("Z", "+00:00")
            last = datetime.fromisoformat(last_s)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (self.clock.now() - last).total_seconds()
            remaining = self.config.interval_seconds - elapsed
            return max(0.0, remaining)
        except Exception:
            return self.config.interval_seconds

    def next_run_iso(self) -> str:
        delta = timedelta(seconds=self.wait_duration())
        nxt = self.clock.now() + delta
        return nxt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def mark_ran(self) -> None:
        self._last_run_iso = self.clock.now_iso()
