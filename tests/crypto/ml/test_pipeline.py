"""Train / predict / artifact / quality gate / strategy bridge."""

from __future__ import annotations

from pathlib import Path

import pytest

from crypto.exchanges.models import OHLCVBar
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.ml import (
    DEFAULT_PROFILE,
    MLPipeline,
    MLProfile,
    available_algorithms,
    load_artifact,
    prediction_to_proposal,
)
from crypto.ml.artifacts import ArtifactError
from crypto.ml.prediction import Direction
from crypto.risk.models import Side


def _bars(n: int = 120) -> list[OHLCVBar]:
    out: list[OHLCVBar] = []
    px = 100.0
    for i in range(n):
        # mild trend + noise
        c = px * (1.0 + (0.002 if i % 4 != 0 else -0.001))
        out.append(
            OHLCVBar(
                timestamp_ms=1_700_000_000_000 + i * 60_000,
                open=px,
                high=max(px, c) * 1.002,
                low=min(px, c) * 0.998,
                close=c,
                volume=5.0 + (i % 7),
            )
        )
        px = c
    return out


def test_fallback_always_available() -> None:
    assert "fallback" in available_algorithms()


def test_ultra_lite_trains_and_predicts() -> None:
    pipe = MLPipeline(profile=MLProfile.ULTRA_LITE)
    assert pipe.select_algorithm() in available_algorithms()
    result = pipe.train(_bars(120))
    assert result.metadata.algorithm in available_algorithms()
    assert result.metadata.training_rows > 0
    pred = pipe.predict(
        "BTC/USDT",
        _bars(120),
        data_quality=DataQualityReport(quality=DataQuality.COMPLETE),
    )
    assert pred.symbol == "BTC/USDT"
    assert pred.direction in (Direction.UP, Direction.DOWN, Direction.NEUTRAL)
    assert 0.0 <= pred.confidence <= 1.0
    assert pred.confidence_calibrated is False
    assert pred.votes  # ensemble-ready


def test_stale_data_not_actionable() -> None:
    pipe = MLPipeline(profile=MLProfile.ULTRA_LITE)
    pipe.train(_bars(100))
    pred = pipe.predict(
        "ETH/USDT",
        _bars(100),
        data_quality=DataQualityReport(quality=DataQuality.STALE, reasons=("stale",)),
    )
    assert pred.data_quality is DataQuality.STALE
    assert pred.is_actionable() is False


def test_save_load_roundtrip(tmp_path: Path) -> None:
    pipe = MLPipeline(profile=MLProfile.ULTRA_LITE)
    pipe.train(_bars(100))
    path = tmp_path / "model"
    pipe.save(str(path))
    model, meta = load_artifact(path)
    pipe2 = MLPipeline(profile=MLProfile.ULTRA_LITE)
    pipe2.load(model, meta)
    pred = pipe2.predict(
        "BTC/USDT",
        _bars(100),
        data_quality=DataQualityReport(quality=DataQuality.COMPLETE),
    )
    assert pred.model_id == meta.model_id


def test_schema_mismatch_rejected(tmp_path: Path) -> None:
    pipe = MLPipeline(profile=MLProfile.ULTRA_LITE)
    pipe.train(_bars(100))
    path = tmp_path / "model"
    pipe.save(str(path))
    # Corrupt schema version
    meta_path = path.with_suffix(".json")
    text = meta_path.read_text(encoding="utf-8").replace(
        '"feature_schema_version": "v1"',
        '"feature_schema_version": "v999"',
    )
    meta_path.write_text(text, encoding="utf-8")
    with pytest.raises(ArtifactError, match="schema"):
        load_artifact(path)


def test_prediction_to_proposal() -> None:
    pipe = MLPipeline(profile=MLProfile.ULTRA_LITE)
    pipe.train(_bars(100))
    pred = pipe.predict(
        "BTC/USDT",
        _bars(100),
        data_quality=DataQualityReport(quality=DataQuality.COMPLETE),
    )
    # Force actionable-like path if model says neutral — still must not crash
    prop = prediction_to_proposal(
        pred, exchange_id="binance", quantity=0.01, price=100.0, min_confidence=0.0
    )
    if pred.direction is Direction.NEUTRAL:
        assert prop is None
    else:
        assert prop is not None
        assert prop.side in (Side.BUY, Side.SELL)
        assert prop.exchange_id == "binance"


def test_train_not_on_predict() -> None:
    pipe = MLPipeline(profile=DEFAULT_PROFILE)
    with pytest.raises(RuntimeError):
        pipe.predict("BTC/USDT", _bars(50))


def test_profile_limits_ultra_lite() -> None:
    from crypto.ml.profiles import limits_for

    lim = limits_for(MLProfile.ULTRA_LITE)
    assert lim.max_threads == 1
    assert "catboost" not in lim.algorithms
    assert lim.max_features <= 20
