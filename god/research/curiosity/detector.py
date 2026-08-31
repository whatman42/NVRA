"""Injectable anomaly detectors — deterministic, no trading decisions."""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from .models import AnomalyDescriptor, AnomalyType, Severity


Observation = dict[str, Any]
DetectorFn = Callable[[Observation], list[AnomalyDescriptor]]


def _severity_from_ratio(ratio: float) -> Severity:
    """Map relative magnitude to severity bands (infrastructure heuristic, not risk law)."""
    if ratio >= 5.0:
        return Severity.CRITICAL
    if ratio >= 3.0:
        return Severity.HIGH
    if ratio >= 2.0:
        return Severity.MEDIUM
    return Severity.LOW


class AnomalyDetector:
    """Compose pluggable detectors over observation dicts."""

    def __init__(self, detectors: Optional[Sequence[DetectorFn]] = None) -> None:
        self._detectors: list[DetectorFn] = list(detectors or default_detectors())

    def detect(self, observation: Observation) -> list[AnomalyDescriptor]:
        if not observation:
            return [
                AnomalyDescriptor(
                    anomaly_type=AnomalyType.DATA,
                    severity=Severity.MEDIUM,
                    score=0.0,
                    detail={"reason": "empty_observation"},
                )
            ]
        found: list[AnomalyDescriptor] = []
        for fn in self._detectors:
            try:
                found.extend(fn(observation))
            except Exception as exc:  # malformed field handling
                found.append(
                    AnomalyDescriptor(
                        anomaly_type=AnomalyType.DATA,
                        severity=Severity.LOW,
                        score=0.0,
                        detail={"reason": "detector_error", "error": str(exc)},
                    )
                )
        return found


def detect_volatility(obs: Observation) -> list[AnomalyDescriptor]:
    vol = obs.get("volatility")
    baseline = obs.get("volatility_baseline")
    if vol is None or baseline is None:
        return []
    try:
        v, b = float(vol), float(baseline)
    except (TypeError, ValueError):
        return [
            AnomalyDescriptor(
                AnomalyType.DATA, Severity.LOW, 0.0, detail={"reason": "malformed_volatility"}
            )
        ]
    if b <= 0:
        return []
    ratio = abs(v / b)
    if ratio < 2.0:
        return []
    return [
        AnomalyDescriptor(
            AnomalyType.VOLATILITY,
            _severity_from_ratio(ratio),
            score=ratio,
            observation_ref=str(obs.get("observation_id") or ""),
            detail={"volatility": v, "baseline": b, "ratio": ratio},
        )
    ]


def detect_volume(obs: Observation) -> list[AnomalyDescriptor]:
    vol = obs.get("volume")
    baseline = obs.get("volume_baseline")
    if vol is None or baseline is None:
        return []
    try:
        v, b = float(vol), float(baseline)
    except (TypeError, ValueError):
        return [
            AnomalyDescriptor(
                AnomalyType.DATA, Severity.LOW, 0.0, detail={"reason": "malformed_volume"}
            )
        ]
    if b <= 0:
        return []
    ratio = abs(v / b)
    if ratio < 2.0:
        return []
    return [
        AnomalyDescriptor(
            AnomalyType.VOLUME,
            _severity_from_ratio(ratio),
            score=ratio,
            observation_ref=str(obs.get("observation_id") or ""),
            detail={"volume": v, "baseline": b, "ratio": ratio},
        )
    ]


def detect_spread(obs: Observation) -> list[AnomalyDescriptor]:
    spread = obs.get("spread")
    baseline = obs.get("spread_baseline")
    if spread is None or baseline is None:
        return []
    try:
        s, b = float(spread), float(baseline)
    except (TypeError, ValueError):
        return [
            AnomalyDescriptor(
                AnomalyType.DATA, Severity.LOW, 0.0, detail={"reason": "malformed_spread"}
            )
        ]
    if b <= 0:
        return []
    ratio = abs(s / b)
    if ratio < 2.0:
        return []
    return [
        AnomalyDescriptor(
            AnomalyType.SPREAD,
            _severity_from_ratio(ratio),
            score=ratio,
            observation_ref=str(obs.get("observation_id") or ""),
            detail={"spread": s, "baseline": b, "ratio": ratio},
        )
    ]


def detect_residual(obs: Observation) -> list[AnomalyDescriptor]:
    residual = obs.get("prediction_residual")
    if residual is None:
        return []
    try:
        r = abs(float(residual))
    except (TypeError, ValueError):
        return [
            AnomalyDescriptor(
                AnomalyType.DATA, Severity.LOW, 0.0, detail={"reason": "malformed_residual"}
            )
        ]
    # Relative to optional scale; default scale=1.0 is mechanical not a trading law
    scale = float(obs.get("residual_scale") or 1.0)
    if scale <= 0:
        scale = 1.0
    ratio = r / scale
    if ratio < 2.0:
        return []
    return [
        AnomalyDescriptor(
            AnomalyType.RESIDUAL,
            _severity_from_ratio(ratio),
            score=ratio,
            observation_ref=str(obs.get("observation_id") or ""),
            detail={"residual": residual, "ratio": ratio},
        )
    ]


def detect_data_quality(obs: Observation) -> list[AnomalyDescriptor]:
    if obs.get("malformed") is True:
        return [
            AnomalyDescriptor(
                AnomalyType.DATA,
                Severity.HIGH,
                score=1.0,
                detail={"reason": "malformed_flag"},
            )
        ]
    return []


def default_detectors() -> list[DetectorFn]:
    return [
        detect_volatility,
        detect_volume,
        detect_spread,
        detect_residual,
        detect_data_quality,
    ]
