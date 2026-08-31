"""Lightweight out-of-distribution / data quality checks for ML inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class OODCheck:
    ok: bool
    status: str  # OK | INSUFFICIENT_DATA | NAN | INF | SCHEMA_MISMATCH | EXTREME
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "reasons": list(self.reasons)}


def check_features(
    X: np.ndarray,
    *,
    expected_n_features: Optional[int] = None,
    max_abs_z: float = 20.0,
) -> OODCheck:
    reasons: list[str] = []
    if X is None or len(X) == 0:
        return OODCheck(False, "INSUFFICIENT_DATA", ("empty",))
    if expected_n_features is not None and X.shape[-1] != expected_n_features:
        return OODCheck(False, "SCHEMA_MISMATCH", ("feature_dim",))
    if np.isnan(X).any():
        reasons.append("nan")
    if np.isinf(X).any():
        reasons.append("inf")
    # extreme relative to batch
    if X.size and np.nanstd(X) > 0:
        z = np.abs((X - np.nanmean(X)) / (np.nanstd(X) + 1e-12))
        if float(np.nanmax(z)) > max_abs_z:
            reasons.append("extreme")
    if "nan" in reasons:
        return OODCheck(False, "NAN", tuple(reasons))
    if "inf" in reasons:
        return OODCheck(False, "INF", tuple(reasons))
    if "extreme" in reasons:
        return OODCheck(False, "EXTREME", tuple(reasons))
    return OODCheck(True, "OK", ())
