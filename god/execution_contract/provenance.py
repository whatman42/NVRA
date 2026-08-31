"""Provenance helpers for N.U.N.G. Phase 5A execution contract."""

from __future__ import annotations

from typing import Any

from .models import build_exec_provenance


def attach_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_exec_provenance(payload)
