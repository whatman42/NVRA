"""LIVE execution profiling — compare to adversarial safety envelope."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExecutionProfileSample:
    signal_ms: int = 0
    risk_approved_ms: int = 0
    submit_ms: int = 0
    ack_ms: int = 0
    fill_ms: int = 0
    expected_price: float = 0.0
    actual_price: float = 0.0
    slippage_bps: float = 0.0
    fee: float = 0.0
    latency_ms: float = 0.0
    partial: bool = False
    rejected: bool = False
    mode: str = "PAPER"


@dataclass
class ExecutionProfiler:
    samples: list[ExecutionProfileSample] = field(default_factory=list)
    max_samples: int = 200

    def record(self, sample: ExecutionProfileSample) -> None:
        self.samples.append(sample)
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples :]

    def mean_slippage_bps(self) -> float | None:
        live = [s for s in self.samples if s.mode == "LIVE" and not s.rejected]
        if not live:
            return None
        return sum(s.slippage_bps for s in live) / len(live)

    def mean_latency_ms(self) -> float | None:
        live = [s for s in self.samples if s.mode == "LIVE" and not s.rejected]
        if not live:
            return None
        return sum(s.latency_ms for s in live) / len(live)

    def exceeds_safety(
        self,
        *,
        max_slippage_bps: float,
        max_latency_ms: float,
        min_samples: int = 3,
    ) -> bool:
        if len([s for s in self.samples if s.mode == "LIVE"]) < min_samples:
            return False
        slip = self.mean_slippage_bps()
        lat = self.mean_latency_ms()
        if slip is not None and slip > max_slippage_bps:
            return True
        return bool(lat is not None and lat > max_latency_ms)
