"""Deterministic chronological labels — no future leakage into features."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from crypto.exchanges.models import OHLCVBar
from crypto.ml.prediction import Direction


@dataclass(frozen=True, slots=True)
class LabelConfig:
    """Horizon in bars; thresholds on forward return."""

    horizon_bars: int = 5
    up_threshold: float = 0.002  # +0.2%
    down_threshold: float = -0.002  # -0.2%


def forward_return(bars: Sequence[OHLCVBar], index: int, horizon: int) -> float | None:
    """Return from close[index] to close[index+horizon]. None if insufficient future."""
    j = index + horizon
    if j >= len(bars):
        return None
    c0 = bars[index].close
    if c0 == 0:
        return None
    return (bars[j].close - c0) / c0


def label_direction(ret: float, cfg: LabelConfig) -> Direction:
    if ret >= cfg.up_threshold:
        return Direction.UP
    if ret <= cfg.down_threshold:
        return Direction.DOWN
    return Direction.NEUTRAL


def direction_to_int(d: Direction) -> int:
    return {Direction.DOWN: 0, Direction.NEUTRAL: 1, Direction.UP: 2}[d]


def int_to_direction(v: int) -> Direction:
    return {0: Direction.DOWN, 1: Direction.NEUTRAL, 2: Direction.UP}.get(v, Direction.NEUTRAL)


def build_labels(
    bars: Sequence[OHLCVBar],
    indices: Sequence[int],
    cfg: LabelConfig | None = None,
) -> list[Direction | None]:
    """Labels aligned with feature indices. Trailing bars without horizon → None."""
    cfg = cfg or LabelConfig()
    out: list[Direction | None] = []
    for i in indices:
        ret = forward_return(bars, i, cfg.horizon_bars)
        if ret is None:
            out.append(None)
        else:
            out.append(label_direction(ret, cfg))
    return out


def chronological_split(
    n: int,
    *,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
) -> tuple[range, range, range]:
    """Time-ordered train / validate / test index ranges into [0, n)."""
    if n <= 0:
        return range(0), range(0), range(0)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    n_test = n - n_train - n_val
    if n_test < 0:
        n_test = 0
        n_val = n - n_train
    return (
        range(0, n_train),
        range(n_train, n_train + n_val),
        range(n_train + n_val, n_train + n_val + n_test),
    )
