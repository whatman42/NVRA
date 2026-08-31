"""Provenance helpers for N.U.N.G. shadow decisions."""

from __future__ import annotations

from typing import Any

from .models import build_decision_provenance


def attach_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_decision_provenance(payload)
