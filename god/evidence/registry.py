"""Append-only Evidence Registry.

Stores ReviewArtifacts. Finalized artifacts must not be mutated in place.
Corrections produce new artifacts that reference the previous one via parent_artifact_id.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import json
import threading
from .models import ReviewArtifact, PromotionState


class EvidenceRegistry:
    """File-backed append-only registry of ReviewArtifacts.

    Designed for simplicity and auditability. Not a high-throughput store.
    """

    def __init__(self, root: str | Path = "evidence_registry") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        self._lock = threading.RLock()
        self._ensure_index()

    def _ensure_index(self) -> None:
        if not self._index_path.exists():
            self._write_index([])

    def _read_index(self) -> List[dict]:
        with self._lock:
            if not self._index_path.exists():
                return []
            try:
                data = json.loads(self._index_path.read_text(encoding="utf-8"))
                return list(data.get("artifacts") or [])
            except (json.JSONDecodeError, OSError):
                return []

    def _write_index(self, entries: List[dict]) -> None:
        with self._lock:
            payload = {"artifacts": entries, "version": 1}
            self._index_path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )

    def append(self, artifact: ReviewArtifact) -> str:
        """Append a new ReviewArtifact. Returns artifact_id."""
        with self._lock:
            path = self.root / f"{artifact.artifact_id}.json"
            path.write_text(artifact.to_json(), encoding="utf-8")

            index = self._read_index()
            index.append({
                "artifact_id": artifact.artifact_id,
                "commit_sha": artifact.commit_sha,
                "timestamp": artifact.timestamp,
                "decision": artifact.decision.value,
                "promotion_state": artifact.promotion_state.value,
                "reviewer_mode": artifact.reviewer_mode.value,
                "parent_artifact_id": artifact.parent_artifact_id,
            })
            self._write_index(index)
            return artifact.artifact_id

    def get(self, artifact_id: str) -> Optional[ReviewArtifact]:
        path = self.root / f"{artifact_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReviewArtifact.from_dict(data)
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            return None

    def list_recent(self, limit: int = 20) -> List[dict]:
        index = self._read_index()
        return list(reversed(index[-limit:]))

    def latest_for_commit(self, commit_sha: str) -> Optional[ReviewArtifact]:
        index = self._read_index()
        for entry in reversed(index):
            if entry.get("commit_sha") == commit_sha:
                return self.get(entry["artifact_id"])
        return None

    def latest_promoted(self) -> Optional[ReviewArtifact]:
        index = self._read_index()
        for entry in reversed(index):
            if entry.get("promotion_state") == PromotionState.PROMOTED.value:
                return self.get(entry["artifact_id"])
        return None
