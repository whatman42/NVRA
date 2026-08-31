"""Provenance helpers for N.U.N.G. paper simulation."""

from __future__ import annotations

from typing import Any

from .models import build_paper_provenance


def attach_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_paper_provenance(payload)
