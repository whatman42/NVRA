"""Orchestration checkpoints — integrity via content hash, not execution authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional


def _hash_payload(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass
class Checkpoint:
    checkpoint_id: str
    context_id: str
    stage: str
    node: str
    event_refs: list[str] = field(default_factory=list)
    content_hash: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "context_id": self.context_id,
            "stage": self.stage,
            "node": self.node,
            "event_refs": list(self.event_refs),
            "content_hash": self.content_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Checkpoint":
        return cls(
            checkpoint_id=str(d["checkpoint_id"]),
            context_id=str(d["context_id"]),
            stage=str(d.get("stage") or ""),
            node=str(d.get("node") or ""),
            event_refs=list(d.get("event_refs") or []),
            content_hash=str(d.get("content_hash") or ""),
            created_at=str(d.get("created_at") or ""),
        )


def make_checkpoint(
    context_id: str,
    stage: str,
    node: str,
    event_refs: list[str],
    *,
    created_at: str = "",
) -> Checkpoint:
    body = {
        "context_id": context_id,
        "stage": stage,
        "node": node,
        "event_refs": list(event_refs),
    }
    content_hash = _hash_payload(body)
    checkpoint_id = "cp-" + content_hash[:24]
    return Checkpoint(
        checkpoint_id=checkpoint_id,
        context_id=context_id,
        stage=stage,
        node=node,
        event_refs=list(event_refs),
        content_hash=content_hash,
        created_at=created_at,
    )


def verify_checkpoint(cp: Checkpoint) -> bool:
    if not cp or not cp.checkpoint_id or not cp.context_id:
        return False
    body = {
        "context_id": cp.context_id,
        "stage": cp.stage,
        "node": cp.node,
        "event_refs": list(cp.event_refs),
    }
    expected = _hash_payload(body)
    return cp.content_hash == expected
