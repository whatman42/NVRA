"""Clock abstraction for N.U.N.G. runtime — injectable, UTC."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...

    def now_iso(self) -> str: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def now_iso(self) -> str:
        return self.now().strftime("%Y-%m-%dT%H:%M:%SZ")


class FixedClock:
    """Deterministic clock for tests."""

    def __init__(self, iso: str = "2020-06-15T12:00:00Z") -> None:
        self._iso = iso
        # parse loosely
        s = iso.replace("Z", "+00:00")
        try:
            self._dt = datetime.fromisoformat(s)
            if self._dt.tzinfo is None:
                self._dt = self._dt.replace(tzinfo=timezone.utc)
        except ValueError:
            self._dt = datetime(2020, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            self._iso = "2020-06-15T12:00:00Z"

    def now(self) -> datetime:
        return self._dt

    def now_iso(self) -> str:
        return self._iso

    def advance_seconds(self, seconds: float) -> None:
        from datetime import timedelta

        self._dt = self._dt + timedelta(seconds=seconds)
        self._iso = self._dt.strftime("%Y-%m-%dT%H:%M:%SZ")
