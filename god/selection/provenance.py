"""Provenance helpers for selection artifacts."""

from __future__ import annotations

from typing import Any

from god.research.provenance import build_provenance_dict, content_hash


def selection_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_provenance_dict(origin="selection_4i", payload=payload)


def fingerprint(parts: dict[str, Any]) -> str:
    return content_hash(parts)
