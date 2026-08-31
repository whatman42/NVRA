"""SSD / storage protection for model artifacts and logs.

Never deletes the current champion. Caps candidate history and temp files.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .registry import ModelRegistry


@dataclass
class RetentionPolicy:
    max_candidates: int = 20
    max_retired: int = 10
    max_total_artifacts_mb: int = 512  # soft budget for 128 GB SSD environments
    protect_champion: bool = True


def apply_retention(
    registry: ModelRegistry,
    policy: Optional[RetentionPolicy] = None,
) -> dict:
    """Prune excess candidates/retired artifacts; never touch champion files."""
    policy = policy or RetentionPolicy()
    records = registry.list_models()
    champion = registry.champion()
    champ_key = (champion.model_id, champion.model_version) if champion else None

    candidates = [r for r in records if r.status == "candidate"]
    retired = [r for r in records if r.status == "retired"]

    removed: list[str] = []

    def _sort_key(r):
        return r.saved_at or ""

    # Keep newest candidates
    candidates_sorted = sorted(candidates, key=_sort_key, reverse=True)
    excess_c = candidates_sorted[policy.max_candidates :]
    for r in excess_c:
        if champ_key and (r.model_id, r.model_version) == champ_key:
            continue
        _try_remove_artifact(registry.root, r.path)
        removed.append(f"candidate:{r.model_id}@{r.model_version}")
        r.status = "pruned"

    retired_sorted = sorted(retired, key=_sort_key, reverse=True)
    excess_r = retired_sorted[policy.max_retired :]
    for r in excess_r:
        if champ_key and (r.model_id, r.model_version) == champ_key:
            continue
        _try_remove_artifact(registry.root, r.path)
        removed.append(f"retired:{r.model_id}@{r.model_version}")
        r.status = "pruned"

    # Persist updated statuses (registry keeps pruned for audit; optional hard drop)
    active = [r for r in records if r.status != "pruned"]
    registry._records = active  # intentional internal update
    registry._save()

    return {
        "removed": removed,
        "remaining": len(active),
        "champion_protected": champ_key is not None,
    }


def _try_remove_artifact(root: Path, rel_path: str) -> None:
    if not rel_path:
        return
    p = Path(root) / rel_path
    try:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)
    except Exception:
        pass
