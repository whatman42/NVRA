"""PAPER/LIVE training isolation."""

from __future__ import annotations

import pytest

from crypto.execution.models import ExecutionMode
from crypto.ml.provenance import (
    DataProvenance,
    LabeledRow,
    ProvenancePolicyError,
    assert_training_allowed,
    filter_for_training,
)


def _row(prov: DataProvenance) -> LabeledRow:
    return LabeledRow(features=(1.0, 2.0), label=1.0, provenance=prov)


def test_live_training_blocks_paper() -> None:
    rows = [_row(DataProvenance.PAPER), _row(DataProvenance.LIVE)]
    with pytest.raises(ProvenancePolicyError):
        assert_training_allowed(rows, target_mode=ExecutionMode.LIVE)


def test_paper_only_dataset_zero_live_rows() -> None:
    rows = [_row(DataProvenance.PAPER), _row(DataProvenance.PAPER)]
    eligible = filter_for_training(rows, target_mode=ExecutionMode.LIVE)
    assert len(eligible) == 0
    with pytest.raises(ProvenancePolicyError):
        assert_training_allowed(rows, target_mode=ExecutionMode.LIVE)


def test_paper_training_ok() -> None:
    rows = [_row(DataProvenance.PAPER)]
    out = assert_training_allowed(rows, target_mode=ExecutionMode.PAPER)
    assert len(out) == 1
