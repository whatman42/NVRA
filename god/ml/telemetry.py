"""ML operational telemetry — inference & training metrics (evidence only).

Never enables LIVE or order_send. Structured, deterministic, lightweight.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InferenceEvent:
    ts: str
    model_id: str
    model_version: str
    latency_ms: float
    confidence: float
    allow_trade: bool
    regime: str = ""
    ood: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "latency_ms": self.latency_ms,
            "confidence": self.confidence,
            "allow_trade": self.allow_trade,
            "regime": self.regime,
            "ood": self.ood,
            "notes": self.notes,
        }


@dataclass
class TrainingEvent:
    ts: str
    model_id: str
    model_version: str
    n_samples: int
    duration_ms: float
    oos_accuracy: float = 0.0
    status: str = "ok"  # ok | deferred | failed
    reason: str = ""
    profile: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "n_samples": self.n_samples,
            "duration_ms": self.duration_ms,
            "oos_accuracy": self.oos_accuracy,
            "status": self.status,
            "reason": self.reason,
            "profile": self.profile,
        }


@dataclass
class TelemetrySummary:
    inference_count: int = 0
    train_count: int = 0
    mean_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    mean_confidence: float = 0.0
    block_rate: float = 0.0
    last_inference_ts: str = ""
    last_train_ts: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "inference_count": self.inference_count,
            "train_count": self.train_count,
            "mean_latency_ms": self.mean_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "mean_confidence": self.mean_confidence,
            "block_rate": self.block_rate,
            "last_inference_ts": self.last_inference_ts,
            "last_train_ts": self.last_train_ts,
        }


class MLTelemetry:
    """Ring-buffer telemetry for inference and training. Fail-closed, no I/O side effects."""

    def __init__(self, max_events: int = 500) -> None:
        self._inf: deque[InferenceEvent] = deque(maxlen=max_events)
        self._trn: deque[TrainingEvent] = deque(maxlen=max_events)

    def record_inference(
        self,
        *,
        model_id: str,
        model_version: str,
        latency_ms: float,
        confidence: float,
        allow_trade: bool,
        regime: str = "",
        ood: bool = False,
        notes: str = "",
    ) -> InferenceEvent:
        ev = InferenceEvent(
            ts=_utc_now(),
            model_id=model_id,
            model_version=model_version,
            latency_ms=float(latency_ms),
            confidence=float(confidence),
            allow_trade=bool(allow_trade),
            regime=regime,
            ood=bool(ood),
            notes=notes,
        )
        self._inf.append(ev)
        return ev

    def record_training(
        self,
        *,
        model_id: str,
        model_version: str,
        n_samples: int,
        duration_ms: float,
        oos_accuracy: float = 0.0,
        status: str = "ok",
        reason: str = "",
        profile: str = "",
    ) -> TrainingEvent:
        ev = TrainingEvent(
            ts=_utc_now(),
            model_id=model_id,
            model_version=model_version,
            n_samples=int(n_samples),
            duration_ms=float(duration_ms),
            oos_accuracy=float(oos_accuracy),
            status=status,
            reason=reason,
            profile=profile,
        )
        self._trn.append(ev)
        return ev

    def summary(self) -> TelemetrySummary:
        inf = list(self._inf)
        trn = list(self._trn)
        lat = [e.latency_ms for e in inf]
        conf = [e.confidence for e in inf]
        blocks = sum(1 for e in inf if not e.allow_trade)
        mean_lat = float(sum(lat) / len(lat)) if lat else 0.0
        p95 = 0.0
        if lat:
            s = sorted(lat)
            idx = min(len(s) - 1, int(0.95 * len(s)))
            p95 = float(s[idx])
        return TelemetrySummary(
            inference_count=len(inf),
            train_count=len(trn),
            mean_latency_ms=mean_lat,
            p95_latency_ms=p95,
            mean_confidence=float(sum(conf) / len(conf)) if conf else 0.0,
            block_rate=float(blocks / len(inf)) if inf else 0.0,
            last_inference_ts=inf[-1].ts if inf else "",
            last_train_ts=trn[-1].ts if trn else "",
        )

    def recent_inferences(self, n: int = 20) -> list[dict[str, Any]]:
        return [e.to_dict() for e in list(self._inf)[-n:]]

    def recent_trainings(self, n: int = 10) -> list[dict[str, Any]]:
        return [e.to_dict() for e in list(self._trn)[-n:]]
