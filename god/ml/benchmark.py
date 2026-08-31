"""Model benchmarking layer — chronological / walk-forward evaluation.

Measures accuracy, precision, recall, brier, log-loss, latency, resource notes.
Never uses future data. Deterministic given same seed + data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np

from .evaluate import EvalReport, evaluate_binary
from .hardware import ResourceGovernor
from .regime import Regime, detect_regime, regime_masks
from .split import TimeSeriesSplitSpec, time_series_splits
from .train import TrainedModel, train_baseline_classifier
from .weighting import volatility_sample_weights


@dataclass
class BenchmarkMetrics:
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    brier: float = 0.0
    log_loss: float = 0.0
    n: int = 0
    latency_ms: float = 0.0
    regime: str = ""
    family: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "brier": self.brier,
            "log_loss": self.log_loss,
            "n": self.n,
            "latency_ms": self.latency_ms,
            "regime": self.regime,
            "family": self.family,
        }


@dataclass
class FamilyBenchmark:
    family: str
    overall: BenchmarkMetrics = field(default_factory=BenchmarkMetrics)
    by_regime: dict[str, BenchmarkMetrics] = field(default_factory=dict)
    model: Optional[TrainedModel] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "overall": self.overall.to_dict(),
            "by_regime": {k: v.to_dict() for k, v in self.by_regime.items()},
            "notes": list(self.notes),
        }


@dataclass
class BenchmarkReport:
    families: list[FamilyBenchmark] = field(default_factory=list)
    ranking: list[str] = field(default_factory=list)
    best_family: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "families": [f.to_dict() for f in self.families],
            "ranking": list(self.ranking),
            "best_family": self.best_family,
            "notes": list(self.notes),
        }


def _precision_recall(y: np.ndarray, pred: np.ndarray) -> tuple[float, float]:
    tp = float(np.sum((pred == 1) & (y == 1)))
    fp = float(np.sum((pred == 1) & (y == 0)))
    fn = float(np.sum((pred == 0) & (y == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def _metrics_from_proba(
    y: np.ndarray, p: np.ndarray, *, family: str = "", regime: str = "", latency_ms: float = 0.0
) -> BenchmarkMetrics:
    if len(y) == 0:
        return BenchmarkMetrics(family=family, regime=regime, latency_ms=latency_ms)
    rep = evaluate_binary(y, p)
    pred = (p >= 0.5).astype(int)
    prec, rec = _precision_recall(y, pred)
    return BenchmarkMetrics(
        accuracy=rep.accuracy,
        precision=prec,
        recall=rec,
        brier=rep.brier,
        log_loss=rep.log_loss,
        n=rep.n,
        latency_ms=latency_ms,
        regime=regime,
        family=family,
    )


def benchmark_family(
    X: np.ndarray,
    y: np.ndarray,
    *,
    family: str,
    feature_names: tuple[str, ...],
    features_version: str = "feat-v1",
    split_spec: Optional[TimeSeriesSplitSpec] = None,
    closes_for_regime: Optional[np.ndarray] = None,
    sample_returns: Optional[np.ndarray] = None,
) -> FamilyBenchmark:
    """Walk-forward benchmark one family. Chronological only."""
    spec = split_spec or TimeSeriesSplitSpec()
    notes: list[str] = []
    if len(X) < 20:
        return FamilyBenchmark(family=family, notes=["insufficient_data"])

    oos_y: list[float] = []
    oos_p: list[float] = []
    last_model: Optional[TrainedModel] = None
    latencies: list[float] = []

    for fold_i, (tr, te) in enumerate(time_series_splits(len(X), spec)):
        if len(tr) < 10 or len(te) < 3:
            continue
        # Optional sample weights on train only
        w = None
        if sample_returns is not None and len(sample_returns) == len(y):
            w = volatility_sample_weights(sample_returns[tr])
        try:
            model = train_baseline_classifier(
                X[tr],
                y[tr],
                feature_names=feature_names,
                features_version=features_version,
                model_id=family,
                model_version=str(fold_i + 1),
            )
        except Exception as e:
            notes.append(f"train_fail:{type(e).__name__}")
            continue
        t0 = time.perf_counter()
        p = model.predict_proba_positive(X[te])
        latencies.append((time.perf_counter() - t0) * 1000.0)
        oos_y.extend(y[te].tolist())
        oos_p.extend(p.tolist())
        last_model = model

    if not oos_y:
        return FamilyBenchmark(family=family, notes=notes or ["no_oos"])

    ya = np.asarray(oos_y)
    pa = np.asarray(oos_p)
    overall = _metrics_from_proba(
        ya,
        pa,
        family=family,
        latency_ms=float(np.mean(latencies)) if latencies else 0.0,
    )

    by_regime: dict[str, BenchmarkMetrics] = {}
    if closes_for_regime is not None and len(closes_for_regime) >= len(X):
        # Approximate: use overall regime on full series for reporting
        snap = detect_regime(closes_for_regime)
        by_regime[snap.regime.value] = overall

    return FamilyBenchmark(
        family=family,
        overall=overall,
        by_regime=by_regime,
        model=last_model,
        notes=notes or ["ok"],
    )


def benchmark_families(
    X: np.ndarray,
    y: np.ndarray,
    families: Sequence[str],
    *,
    feature_names: tuple[str, ...],
    features_version: str = "feat-v1",
    governor: Optional[ResourceGovernor] = None,
    closes_for_regime: Optional[np.ndarray] = None,
    sample_returns: Optional[np.ndarray] = None,
) -> BenchmarkReport:
    """Benchmark allowed families under resource limits; rank by OOS quality."""
    gov = governor or ResourceGovernor()
    allowed = [f for f in families if gov.family_allowed(f) or f in ("numpy_logit", "random_forest")]
    if not gov.limits.training_allowed:
        return BenchmarkReport(notes=["training_blocked_by_pressure"])

    results: list[FamilyBenchmark] = []
    for fam in allowed:
        if fam in ("lstm", "gru", "transformer") and not gov.limits.allow_heavy_ml:
            continue
        fb = benchmark_family(
            X,
            y,
            family=fam,
            feature_names=feature_names,
            features_version=features_version,
            closes_for_regime=closes_for_regime,
            sample_returns=sample_returns,
        )
        results.append(fb)

    # Rank: higher accuracy, lower brier; require n >= 5
    def score(fb: FamilyBenchmark) -> float:
        m = fb.overall
        if m.n < 5:
            return -1.0
        return m.accuracy - 0.5 * m.brier

    ranked = sorted(results, key=score, reverse=True)
    ranking = [r.family for r in ranked if r.overall.n >= 5]
    best = ranking[0] if ranking else (results[0].family if results else "numpy_logit")
    return BenchmarkReport(
        families=results,
        ranking=ranking,
        best_family=best,
        notes=["benchmark_complete"] if results else ["no_results"],
    )
