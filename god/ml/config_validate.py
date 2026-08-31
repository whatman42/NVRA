"""ML configuration validation — fail-closed on invalid / unsafe settings.

Never enables LIVE. Validates Adaptive ML runtime config before use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Hard safety defaults that must never be overridden to True for LIVE paths
_FORBIDDEN_TRUE = frozenset(
    {
        "live_authorized",
        "LIVE_AUTHORIZED",
        "enable_live",
        "auto_live",
        "broker_orders_enabled",
        "order_send_from_ml",
    }
)


@dataclass
class ConfigValidationResult:
    valid: bool
    reasons: list[str] = field(default_factory=list)
    normalized: dict[str, Any] = field(default_factory=dict)
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reasons": list(self.reasons),
            "normalized": dict(self.normalized),
            "checked_at": self.checked_at,
        }


@dataclass
class MLRuntimeConfig:
    """Validated runtime knobs for Adaptive ML (paper/DEMO only)."""

    meta_enabled: bool = False
    min_samples_train: int = 50
    min_samples_promote: int = 30
    max_ensemble_size: int = 3
    inference_priority: bool = True
    allow_heavy_ml: bool = False
    telemetry_max_events: int = 500
    audit_max_entries: int = 1000
    health_max_block_rate: float = 0.85
    data_quality_min_samples: int = 30

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta_enabled": self.meta_enabled,
            "min_samples_train": self.min_samples_train,
            "min_samples_promote": self.min_samples_promote,
            "max_ensemble_size": self.max_ensemble_size,
            "inference_priority": self.inference_priority,
            "allow_heavy_ml": self.allow_heavy_ml,
            "telemetry_max_events": self.telemetry_max_events,
            "audit_max_entries": self.audit_max_entries,
            "health_max_block_rate": self.health_max_block_rate,
            "data_quality_min_samples": self.data_quality_min_samples,
            "live_authorized": False,
            "broker_orders_submitted": 0,
        }


def validate_ml_config(raw: Optional[dict[str, Any]] = None) -> ConfigValidationResult:
    """Validate and normalize ML runtime config. Fail-closed on unsafe keys."""
    raw = dict(raw or {})
    reasons: list[str] = []

    # Block any attempt to enable LIVE via config
    for key in _FORBIDDEN_TRUE:
        if key in raw and bool(raw[key]):
            reasons.append(f"forbidden_true:{key}")

    # Also reject if nested under safety
    safety = raw.get("safety") if isinstance(raw.get("safety"), dict) else {}
    for key in _FORBIDDEN_TRUE:
        if key in safety and bool(safety[key]):
            reasons.append(f"forbidden_true_safety:{key}")

    cfg = MLRuntimeConfig()
    if "meta_enabled" in raw:
        cfg.meta_enabled = bool(raw["meta_enabled"])
    if "min_samples_train" in raw:
        try:
            v = int(raw["min_samples_train"])
            if v < 10:
                reasons.append("min_samples_train_too_low")
            else:
                cfg.min_samples_train = v
        except (TypeError, ValueError):
            reasons.append("min_samples_train_invalid")
    if "min_samples_promote" in raw:
        try:
            v = int(raw["min_samples_promote"])
            if v < 5:
                reasons.append("min_samples_promote_too_low")
            else:
                cfg.min_samples_promote = v
        except (TypeError, ValueError):
            reasons.append("min_samples_promote_invalid")
    if "max_ensemble_size" in raw:
        try:
            v = int(raw["max_ensemble_size"])
            if v < 1 or v > 10:
                reasons.append("max_ensemble_size_out_of_range")
            else:
                cfg.max_ensemble_size = v
        except (TypeError, ValueError):
            reasons.append("max_ensemble_size_invalid")
    if "inference_priority" in raw:
        cfg.inference_priority = bool(raw["inference_priority"])
    if "allow_heavy_ml" in raw:
        cfg.allow_heavy_ml = bool(raw["allow_heavy_ml"])
    if "telemetry_max_events" in raw:
        try:
            v = int(raw["telemetry_max_events"])
            cfg.telemetry_max_events = max(10, min(v, 10000))
        except (TypeError, ValueError):
            reasons.append("telemetry_max_events_invalid")
    if "audit_max_entries" in raw:
        try:
            v = int(raw["audit_max_entries"])
            cfg.audit_max_entries = max(10, min(v, 50000))
        except (TypeError, ValueError):
            reasons.append("audit_max_entries_invalid")
    if "health_max_block_rate" in raw:
        try:
            v = float(raw["health_max_block_rate"])
            if not (0.0 < v <= 1.0):
                reasons.append("health_max_block_rate_out_of_range")
            else:
                cfg.health_max_block_rate = v
        except (TypeError, ValueError):
            reasons.append("health_max_block_rate_invalid")
    if "data_quality_min_samples" in raw:
        try:
            v = int(raw["data_quality_min_samples"])
            if v < 5:
                reasons.append("data_quality_min_samples_too_low")
            else:
                cfg.data_quality_min_samples = v
        except (TypeError, ValueError):
            reasons.append("data_quality_min_samples_invalid")

    # Hard force safety fields
    normalized = cfg.to_dict()
    normalized["live_authorized"] = False
    normalized["broker_orders_submitted"] = 0

    valid = len(reasons) == 0
    return ConfigValidationResult(
        valid=valid,
        reasons=reasons,
        normalized=normalized,
        checked_at=_utc_now(),
    )
