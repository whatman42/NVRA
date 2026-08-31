"""Correlation / trace IDs for N.U.N.G. cognitive pipeline."""

from __future__ import annotations

from typing import Optional

from .models import make_correlation_id


def correlate(
    *,
    snapshot_id: Optional[str] = None,
    cycle_id: Optional[str] = None,
    version: str = "control-4o-v1",
) -> str:
    return make_correlation_id(snapshot_id, cycle_id, version)
