"""Data provenance helpers — content hashing and lineage records."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now

from .models import ProvenanceRecord


def content_hash(payload: str | bytes | dict | list) -> str:
    """Deterministic SHA-256 of normalized payload."""
    if isinstance(payload, bytes):
        data = payload
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def build_provenance_dict(
    *,
    origin: str,
    payload: str | bytes | dict | list,
) -> dict[str, str]:
    """Build the stable dictionary representation used by domain wrappers."""
    prov = build_provenance(origin=origin, payload=payload)
    return {
        "provenance_id": prov.provenance_id,
        "content_hash": prov.content_hash,
        "origin": prov.origin,
    }


def build_provenance(
    *,
    origin: str,
    payload: str | bytes | dict | list,
    source_id: Optional[str] = None,
    raw_ref: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> ProvenanceRecord:
    return ProvenanceRecord(
        provenance_id=str(uuid4()),
        source_id=source_id,
        origin=origin,
        retrieved_at=utc_now(),
        content_hash=content_hash(payload),
        raw_ref=raw_ref,
        metadata=dict(metadata or {}),
    )
