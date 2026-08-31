"""Pure-Python fallback model for ULTRA_LITE / missing optional deps.

Simple majority-class + feature threshold stumps. Deterministic, no numpy.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Sequence

from crypto.ml.base import BaseModel


class FallbackModel(BaseModel):
    algorithm = "fallback"

    def __init__(self) -> None:
        self._majority = 1  # NEUTRAL
        self._stumps: list[tuple[int, float, int, int]] = []  # feat, thresh, left, right
        self._feature_names: tuple[str, ...] = ()
        self._fitted = False

    def fit(
        self,
        x: Sequence[Sequence[float]],
        y: Sequence[int],
        *,
        feature_names: Sequence[str],
    ) -> None:
        if not x or not y:
            raise ValueError("empty training set")
        self._feature_names = tuple(feature_names)
        counts = [0, 0, 0]
        for label in y:
            counts[int(label)] += 1
        self._majority = max(range(3), key=lambda i: counts[i])

        n_features = len(x[0])
        self._stumps = []
        # Up to 5 shallow stumps on first features
        for fi in range(min(5, n_features)):
            vals = sorted({row[fi] for row in x})
            if len(vals) < 2:
                continue
            thresh = vals[len(vals) // 2]
            left_c = [0, 0, 0]
            right_c = [0, 0, 0]
            for row, label in zip(x, y, strict=True):
                if row[fi] <= thresh:
                    left_c[int(label)] += 1
                else:
                    right_c[int(label)] += 1
            left = max(range(3), key=lambda i: left_c[i])
            right = max(range(3), key=lambda i: right_c[i])
            self._stumps.append((fi, float(thresh), left, right))
        self._fitted = True

    def predict(self, x: Sequence[Sequence[float]]) -> list[int]:
        proba = self.predict_proba(x)
        return [max(range(3), key=lambda i: p[i]) for p in proba]

    def predict_proba(self, x: Sequence[Sequence[float]]) -> list[tuple[float, float, float]]:
        out: list[tuple[float, float, float]] = []
        for row in x:
            votes = [0.0, 0.0, 0.0]
            votes[self._majority] += 1.0
            for fi, thresh, left, right in self._stumps:
                if fi >= len(row):
                    continue
                cls = left if row[fi] <= thresh else right
                votes[cls] += 1.0
            s = sum(votes) or 1.0
            out.append((votes[0] / s, votes[1] / s, votes[2] / s))
        return out

    def save_bytes(self) -> bytes:
        payload = {
            "majority": self._majority,
            "stumps": self._stumps,
            "feature_names": list(self._feature_names),
        }
        body = json.dumps(payload).encode("utf-8")
        return b"FB01" + struct.pack(">I", len(body)) + body

    @classmethod
    def load_bytes(cls, data: bytes) -> FallbackModel:
        if not data.startswith(b"FB01"):
            raise ValueError("invalid fallback model magic")
        (n,) = struct.unpack(">I", data[4:8])
        payload = json.loads(data[8 : 8 + n].decode("utf-8"))
        m = cls()
        m._majority = int(payload["majority"])
        raw_stumps = payload["stumps"]
        m._stumps = [(int(a), float(b), int(c), int(d)) for a, b, c, d in raw_stumps]
        m._feature_names = tuple(payload["feature_names"])
        m._fitted = True
        return m
