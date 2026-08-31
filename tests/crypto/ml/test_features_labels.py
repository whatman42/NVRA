"""Feature pipeline and leakage tests."""

from __future__ import annotations

from crypto.exchanges.models import OHLCVBar
from crypto.ml.features import FEATURE_NAMES, build_feature_matrix, compute_feature_row
from crypto.ml.labels import LabelConfig, build_labels, chronological_split, forward_return


def _bars(n: int = 80, start_px: float = 100.0) -> list[OHLCVBar]:
    out: list[OHLCVBar] = []
    px = start_px
    for i in range(n):
        o = px
        c = px * (1.0 + (0.001 if i % 3 == 0 else -0.0005))
        h = max(o, c) * 1.001
        low_px = min(o, c) * 0.999
        out.append(
            OHLCVBar(
                timestamp_ms=1_700_000_000_000 + i * 60_000,
                open=o,
                high=h,
                low=low_px,
                close=c,
                volume=10.0 + i,
            )
        )
        px = c
    return out


def test_feature_count() -> None:
    assert 20 <= len(FEATURE_NAMES) <= 40


def test_feature_no_nan() -> None:
    bars = _bars(50)
    row = compute_feature_row(bars, 30)
    assert len(row.values) == len(FEATURE_NAMES)
    assert all(v == v and abs(v) != float("inf") for v in row.values)


def test_leakage_feature_independent_of_future() -> None:
    bars = _bars(40)
    row_a = compute_feature_row(bars, 25)
    # Mutate future bar
    bars[35] = OHLCVBar(
        bars[35].timestamp_ms,
        999,
        999,
        999,
        999,
        999,
    )
    row_b = compute_feature_row(bars, 25)
    assert row_a.values == row_b.values


def test_label_uses_future_only_for_target() -> None:
    bars = _bars(40)
    r = forward_return(bars, 10, 5)
    assert r is not None
    # Changing past should not be required; changing the horizon target does
    bars2 = list(bars)
    bars2[15] = OHLCVBar(
        bars2[15].timestamp_ms,
        bars2[15].open,
        bars2[15].high * 2,
        bars2[15].low,
        bars2[15].close * 2,
        bars2[15].volume,
    )
    r2 = forward_return(bars2, 10, 5)
    assert r2 != r


def test_chronological_split_order() -> None:
    tr, va, te = chronological_split(100)
    assert list(tr)[-1] < list(va)[0]
    assert list(va)[-1] < list(te)[0]


def test_build_matrix_and_labels() -> None:
    bars = _bars(60)
    rows, idx = build_feature_matrix(bars, min_history=20)
    labels = build_labels(bars, idx, LabelConfig(horizon_bars=3))
    assert len(rows) == len(labels)
    # Last few may be None due to horizon
    assert any(lab is None for lab in labels[-3:])
