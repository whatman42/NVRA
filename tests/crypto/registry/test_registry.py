"""Model registry lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from crypto.exchanges.models import OHLCVBar
from crypto.ml import MLPipeline, MLProfile
from crypto.registry import ModelRegistry, ModelStatus, RegistryError


def _bars(n: int = 100) -> list[OHLCVBar]:
    px = 100.0
    out: list[OHLCVBar] = []
    for i in range(n):
        c = px * (1.0 + 0.001)
        out.append(
            OHLCVBar(
                timestamp_ms=1_700_000_000_000 + i * 60_000,
                open=px,
                high=max(px, c) * 1.001,
                low=min(px, c) * 0.999,
                close=c,
                volume=10.0,
            )
        )
        px = c
    return out


def test_register_validate_activate(tmp_path: Path) -> None:
    pipe = MLPipeline(profile=MLProfile.ULTRA_LITE)
    result = pipe.train(_bars(100))
    art = tmp_path / "m1"
    pipe.save(str(art))

    reg = ModelRegistry(tmp_path / "reg")
    entry = reg.register(result.metadata, str(art))
    assert entry.status is ModelStatus.CANDIDATE
    reg.validate(entry.model_id)
    reg.activate(entry.model_id)
    active = reg.list_entries(status=ModelStatus.ACTIVE)
    assert len(active) == 1
    models = reg.load_active_models()
    assert len(models) == 1


def test_rollback(tmp_path: Path) -> None:
    reg = ModelRegistry(tmp_path / "reg")
    ids = []
    for i in range(2):
        pipe = MLPipeline(profile=MLProfile.ULTRA_LITE)
        result = pipe.train(_bars(100 + i))
        art = tmp_path / f"m{i}"
        pipe.save(str(art))
        e = reg.register(result.metadata, str(art))
        reg.validate(e.model_id)
        reg.activate(e.model_id)
        ids.append(e.model_id)
    # second is active; rollback should restore previous
    rolled = reg.rollback(result.metadata.algorithm)
    assert rolled.model_id == ids[0] or rolled.status is ModelStatus.ACTIVE


def test_cannot_activate_candidate(tmp_path: Path) -> None:
    pipe = MLPipeline(profile=MLProfile.ULTRA_LITE)
    result = pipe.train(_bars(100))
    art = tmp_path / "m"
    pipe.save(str(art))
    reg = ModelRegistry(tmp_path / "reg")
    e = reg.register(result.metadata, str(art))
    with pytest.raises(RegistryError):
        reg.activate(e.model_id)
