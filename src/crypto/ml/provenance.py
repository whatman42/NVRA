"""Dataset provenance — hard isolation of PAPER vs LIVE training rows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from crypto.execution.models import ExecutionMode


class DataProvenance(Enum):
    PAPER = auto()
    LIVE = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class LabeledRow:
    """Single training example with mandatory provenance."""

    features: tuple[float, ...]
    label: float
    provenance: DataProvenance
    source_id: str = ""


class ProvenancePolicyError(ValueError):
    """Raised when training data violates PAPER/LIVE isolation."""


def filter_for_training(
    rows: list[LabeledRow],
    *,
    target_mode: ExecutionMode,
) -> list[LabeledRow]:
    """Return only rows eligible for the target training mode.

    LIVE training: only LIVE provenance.
    PAPER training: PAPER (and optionally UNKNOWN blocked).
    """
    allowed = {DataProvenance.LIVE} if target_mode is ExecutionMode.LIVE else {DataProvenance.PAPER}
    return [r for r in rows if r.provenance in allowed]


def assert_training_allowed(
    rows: list[LabeledRow],
    *,
    target_mode: ExecutionMode,
) -> list[LabeledRow]:
    """Hard-block training if any row violates policy or zero eligible rows for LIVE."""
    eligible = filter_for_training(rows, target_mode=target_mode)
    if target_mode is ExecutionMode.LIVE:
        # Explicit: PAPER rows must never slip into LIVE training
        paper_leak = [r for r in rows if r.provenance is DataProvenance.PAPER]
        if paper_leak:
            raise ProvenancePolicyError(
                f"PAPER rows forbidden in LIVE training ({len(paper_leak)} found)"
            )
        unknown = [r for r in rows if r.provenance is DataProvenance.UNKNOWN]
        if unknown:
            raise ProvenancePolicyError("UNKNOWN provenance forbidden in LIVE training")
        if not eligible:
            raise ProvenancePolicyError("0 eligible LIVE training rows")
    return eligible
