"""Production-oriented MarketDataSource for N.U.N.G. — injectable transport, no trading."""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from god.data.circuit import CircuitBreaker, CircuitBreakerConfig, CircuitState
from god.data.health import SourceHealth, SourceHealthState
from god.data.models import MarketBar
from god.data.normalization import normalize_bar
from god.data.rate_limit import RateLimitGuard, parse_rate_limit_from_exception
from god.data.retry import FailureClass, RetryPolicy, classify_exception, run_with_retry
from god.data.single_flight import SingleFlight


@runtime_checkable
class ProviderTransport(Protocol):
    """Injectable transport — tests use FakeProviderTransport. No broker orders."""

    def fetch_universe(self) -> list[str]: ...

    def fetch_bars(self, symbol: str, *, max_bars: Optional[int] = None) -> list[dict[str, Any]]: ...

    def health(self) -> dict[str, Any]: ...


class FakeProviderTransport:
    """Deterministic fake for tests — no network."""

    def __init__(
        self,
        data: Optional[dict[str, list[dict[str, Any]]]] = None,
        *,
        universe: Optional[list[str]] = None,
        health_state: str = "HEALTHY",
        raise_on_fetch: Optional[Exception] = None,
        empty: bool = False,
        fail_times: int = 0,
    ) -> None:
        self._data = {k.upper(): list(v) for k, v in (data or {}).items()}
        self._universe = [s.upper() for s in (universe or list(self._data.keys()))]
        self._health_state = health_state
        self._raise = raise_on_fetch
        self._empty = empty
        self._fail_times = fail_times
        self._fail_remaining = fail_times
        self.fetch_count = 0

    def fetch_universe(self) -> list[str]:
        self.fetch_count += 1
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            if self._raise:
                raise self._raise
            raise ConnectionError("transient")
        if self._raise and self._fail_times == 0:
            raise self._raise
        if self._empty:
            return []
        return list(self._universe)

    def fetch_bars(self, symbol: str, *, max_bars: Optional[int] = None) -> list[dict[str, Any]]:
        self.fetch_count += 1
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            if self._raise:
                raise self._raise
            raise ConnectionError("transient")
        if self._raise and self._fail_times == 0:
            raise self._raise
        bars = list(self._data.get(symbol.upper()) or [])
        if max_bars is not None:
            bars = bars[-max_bars:]
        return bars

    def health(self) -> dict[str, Any]:
        return {"state": self._health_state, "source": "fake"}


class ProductionMarketDataSource:
    """
    Provider-neutral production adapter with retry, circuit breaker, rate-limit guard.
    Transport is injected — no hardcoded broker, no MT5 trading, no credentials in code.
    """

    def __init__(
        self,
        transport: ProviderTransport,
        *,
        source_id: str = "production",
        max_retries: int = 2,
        requested_symbols: Optional[list[str]] = None,
        retry_policy: Optional[RetryPolicy] = None,
        circuit: Optional[CircuitBreaker] = None,
        now_fn: Optional[Any] = None,
    ) -> None:
        self.transport = transport
        self.source_id = source_id
        self.max_retries = max(0, max_retries)
        self.requested_symbols = (
            [s.upper() for s in requested_symbols] if requested_symbols else None
        )
        self.retry_policy = retry_policy or RetryPolicy(max_retries=self.max_retries)
        self.circuit = circuit or CircuitBreaker(
            CircuitBreakerConfig(), now_fn=now_fn or (lambda: 0.0)
        )
        self.rate_limit = RateLimitGuard(now_fn=now_fn or (lambda: 0.0))
        self.single_flight = SingleFlight()
        self._last_health = SourceHealth(
            state=SourceHealthState.UNKNOWN, source_id=source_id
        )
        self._telemetry: dict[str, Any] = {
            "last_success_at": None,
            "last_failure_at": None,
            "last_failure_class": None,
            "retry_count": 0,
            "circuit_state": CircuitState.CLOSED.value,
        }

    def fetch_universe(self) -> list[str]:
        if not self.circuit.allow_request():
            self._last_health = SourceHealth(
                state=SourceHealthState.UNAVAILABLE,
                reason="circuit_open",
                source_id=self.source_id,
                metadata={"circuit": self.circuit.state.value},
            )
            return []
        if not self.rate_limit.allow():
            self._last_health = SourceHealth(
                state=SourceHealthState.DEGRADED,
                reason="rate_limited",
                source_id=self.source_id,
                metadata=self.rate_limit.last_info.to_dict(),
            )
            return []

        def _call() -> list[str]:
            return self.single_flight.do(
                "universe",
                lambda: [str(s).upper() for s in self.transport.fetch_universe()],
            )

        try:
            uni = run_with_retry(_call, self.retry_policy)
            seen: set[str] = set()
            ordered: list[str] = []
            for s in uni:
                if s and s not in seen:
                    seen.add(s)
                    ordered.append(s)
            if self.requested_symbols is not None:
                ordered = [s for s in self.requested_symbols if s in seen] or ordered
            self.circuit.record_success()
            self.rate_limit.clear()
            self._telemetry["last_success_at"] = "ok"
            self._telemetry["circuit_state"] = self.circuit.state.value
            self._last_health = SourceHealth(
                state=SourceHealthState.HEALTHY if ordered else SourceHealthState.UNAVAILABLE,
                reason="ok" if ordered else "empty_universe",
                source_id=self.source_id,
                metadata={
                    "requested_count": len(self.requested_symbols or ordered),
                    "received_count": len(ordered),
                    "circuit": self.circuit.state.value,
                },
            )
            return ordered
        except Exception as exc:
            return self._on_failure(exc, "fetch_universe")

    def fetch_bars(
        self,
        symbol: str,
        *,
        max_bars: Optional[int] = None,
    ) -> list[MarketBar]:
        if not self.circuit.allow_request():
            self._last_health = SourceHealth(
                state=SourceHealthState.UNAVAILABLE,
                reason="circuit_open",
                source_id=self.source_id,
            )
            return []
        if not self.rate_limit.allow():
            return []

        key = f"bars:{symbol.upper()}:{max_bars}"

        def _call() -> list[MarketBar]:
            def _inner() -> list[MarketBar]:
                raw = self.transport.fetch_bars(symbol, max_bars=max_bars)
                bars: list[MarketBar] = []
                for item in raw:
                    if isinstance(item, MarketBar):
                        bars.append(item)
                    elif isinstance(item, dict):
                        b = normalize_bar(symbol, item, source_id=self.source_id)
                        if b is not None:
                            bars.append(b)
                return bars

            return self.single_flight.do(key, _inner)

        try:
            bars = run_with_retry(_call, self.retry_policy)
            self.circuit.record_success()
            self.rate_limit.clear()
            self._telemetry["last_success_at"] = "ok"
            self._telemetry["circuit_state"] = self.circuit.state.value
            return bars
        except Exception as exc:
            self._on_failure(exc, "fetch_bars")
            return []

    def fetch_metadata(self, symbol: str) -> dict[str, Any]:
        return {"source_id": self.source_id, "symbol": symbol.upper()}

    def source_health(self) -> SourceHealth:
        try:
            h = self.transport.health()
            state_s = str(h.get("state", "UNKNOWN")).upper()
            try:
                state = SourceHealthState(state_s)
            except ValueError:
                state = SourceHealthState.UNKNOWN
            # circuit open overrides
            if self.circuit.state == CircuitState.OPEN:
                state = SourceHealthState.UNAVAILABLE
            self._last_health = SourceHealth(
                state=state,
                reason=str(h.get("reason", "")),
                source_id=self.source_id,
                metadata={
                    **dict(h),
                    "circuit": self.circuit.state.value,
                    **self._telemetry,
                },
            )
        except Exception as exc:
            self._last_health = SourceHealth(
                state=SourceHealthState.UNAVAILABLE,
                reason=type(exc).__name__,
                source_id=self.source_id,
            )
        return self._last_health

    def telemetry(self) -> dict[str, Any]:
        return {
            **self._telemetry,
            "circuit_state": self.circuit.state.value,
            "rate_limit": self.rate_limit.last_info.to_dict(),
        }

    def _on_failure(self, exc: BaseException, op: str) -> list:
        fc = classify_exception(exc)
        self.circuit.record_failure()
        rl = parse_rate_limit_from_exception(exc)
        if rl.limited:
            self.rate_limit.block(rl)
        self._telemetry["last_failure_at"] = op
        self._telemetry["last_failure_class"] = fc.value
        self._telemetry["retry_count"] = self.retry_policy.max_retries
        self._telemetry["circuit_state"] = self.circuit.state.value
        state = SourceHealthState.UNAVAILABLE
        if fc == FailureClass.RATE_LIMIT:
            state = SourceHealthState.DEGRADED
        if fc == FailureClass.MALFORMED:
            state = SourceHealthState.CORRUPTED
        self._last_health = SourceHealth(
            state=state,
            reason=f"{op}:{type(exc).__name__}:{fc.value}",
            source_id=self.source_id,
            metadata=self.telemetry(),
        )
        return []
