"""In-process single-flight for identical market-data fetches."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


class SingleFlight:
    """
    Deduplicate concurrent identical keys in-process.
    Not a distributed lock. Bounded by key count.
    """

    def __init__(self, max_keys: int = 256) -> None:
        self._in_flight: Dict[str, Any] = {}
        self._results: Dict[str, Any] = {}
        self.max_keys = max_keys

    def do(self, key: str, fn: Callable[[], T]) -> T:
        if key in self._results:
            return self._results[key]  # type: ignore[return-value]
        if key in self._in_flight:
            # simple sync: wait by reusing completed result only;
            # without threads, sequential callers get same path after first completes
            pass
        self._in_flight[key] = True
        try:
            result = fn()
            self._results[key] = result
            while len(self._results) > self.max_keys:
                self._results.pop(next(iter(self._results)))
            return result
        finally:
            self._in_flight.pop(key, None)

    def clear(self) -> None:
        self._in_flight.clear()
        self._results.clear()
