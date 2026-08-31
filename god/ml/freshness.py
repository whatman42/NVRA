"""Model and dataset freshness — stale detection for recovery and scheduler.

Advisory only. Never enables LIVE. Never auto-promotes.
Stale model/dataset contributes to SAFE_ONLY / prefer_no_trade signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> Optional[float]:
    if not ts:
        return None
    try:
        # support Z and +00:00
        s = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


@dataclass
class FreshnessReport:
    ok: bool
    status: str  # fresh | stale_model | stale_dataset | unknown | missing
    model_age_hours: float = -1.0
    dataset_age_hours: float = -1.0
    reasons: list[str] = field(default_factory=list)
    prefer_no_trade: bool = False
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "model_age_hours": self.model_age_hours,
            "dataset_age_hours": self.dataset_age_hours,
            "reasons": list(self.reasons),
            "prefer_no_trade": self.prefer_no_trade,
            "checked_at": self.checked_at,
        }


@dataclass
class FreshnessPolicy:
    max_model_age_hours: float = 168.0  # 7 days
    max_dataset_age_hours: float = 72.0  # 3 days
    hard_stale_model_hours: float = 720.0  # 30 days → prefer_no_trade


def evaluate_freshness(
    *,
    model_saved_at: str = "",
    dataset_built_at: str = "",
    now_ts: Optional[float] = None,
    policy: Optional[FreshnessPolicy] = None,
) -> FreshnessReport:
    """Deterministic freshness check. Missing timestamps → unknown (not auto-fail)."""
    pol = policy or FreshnessPolicy()
    now = float(now_ts) if now_ts is not None else datetime.now(timezone.utc).timestamp()
    reasons: list[str] = []
    model_age = -1.0
    data_age = -1.0

    mt = _parse_iso(model_saved_at)
    if mt is not None:
        model_age = max(0.0, (now - mt) / 3600.0)
        if model_age > pol.hard_stale_model_hours:
            reasons.append("model_hard_stale")
        elif model_age > pol.max_model_age_hours:
            reasons.append("model_stale")

    dt = _parse_iso(dataset_built_at)
    if dt is not None:
        data_age = max(0.0, (now - dt) / 3600.0)
        if data_age > pol.max_dataset_age_hours:
            reasons.append("dataset_stale")

    if not model_saved_at and not dataset_built_at:
        return FreshnessReport(
            ok=True,
            status="unknown",
            reasons=["no_timestamps"],
            checked_at=_utc_now(),
        )

    hard = "model_hard_stale" in reasons
    soft = bool(reasons) and not hard
    if hard:
        status = "stale_model"
        ok = False
        no_trade = True
    elif soft:
        status = "stale_model" if "model_stale" in reasons else "stale_dataset"
        ok = False
        no_trade = False
    else:
        status = "fresh"
        ok = True
        no_trade = False

    return FreshnessReport(
        ok=ok,
        status=status,
        model_age_hours=model_age,
        dataset_age_hours=data_age,
        reasons=reasons,
        prefer_no_trade=no_trade,
        checked_at=_utc_now(),
    )
