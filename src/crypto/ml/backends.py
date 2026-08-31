"""Optional ML backends. Import failures → algorithm unavailable (not crash)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import io
import pickle

from crypto.ml.base import BaseModel
from crypto.ml.fallback import FallbackModel
from crypto.ml.profiles import ResourceLimits



def _load_trusted_pickle(data: bytes) -> Any:
    """Deserialize an artifact only after its caller authenticated its digest.

    This helper is intentionally private. Callers must verify the artifact against
    a trusted checksum/signature before passing bytes here. Magic headers alone are
    never considered an authentication boundary.
    """
    return pickle.Unpickler(io.BytesIO(data)).load()

def available_algorithms() -> list[str]:
    found = ["fallback"]
    for name, mod in (
        ("lightgbm", "lightgbm"),
        ("xgboost", "xgboost"),
        ("random_forest", "sklearn.ensemble"),
        ("catboost", "catboost"),
    ):
        try:
            __import__(mod)
            found.append(name)
        except ImportError:
            pass
    return found


def create_model(algorithm: str, limits: ResourceLimits) -> BaseModel:
    algo = algorithm.lower()
    if algo == "fallback":
        return FallbackModel()
    if algo == "lightgbm":
        return _LightGBMModel(limits)
    if algo == "xgboost":
        return _XGBoostModel(limits)
    if algo == "random_forest":
        return _RandomForestModel(limits)
    if algo == "catboost":
        return _CatBoostModel(limits)
    raise ValueError(f"unknown algorithm: {algorithm}")


def _pad_proba(row: Any) -> tuple[float, float, float]:
    vals = [float(v) for v in list(row)]
    while len(vals) < 3:
        vals.append(0.0)
    total = sum(vals[:3]) or 1.0
    return (vals[0] / total, vals[1] / total, vals[2] / total)


class _LightGBMModel(BaseModel):
    algorithm = "lightgbm"

    def __init__(self, limits: ResourceLimits) -> None:
        self._limits = limits
        self._model: Any = None

    def fit(
        self,
        x: Sequence[Sequence[float]],
        y: Sequence[int],
        *,
        feature_names: Sequence[str],
    ) -> None:
        import lightgbm as lgb
        import numpy as np

        arr = np.asarray(x, dtype=float)
        labels = np.asarray(y, dtype=int)
        self._model = lgb.LGBMClassifier(
            n_estimators=self._limits.max_trees,
            max_depth=self._limits.max_depth,
            num_leaves=min(31, 2 ** max(1, self._limits.max_depth)),
            n_jobs=self._limits.max_threads,
            verbose=-1,
        )
        self._model.fit(arr, labels)

    def predict(self, x: Sequence[Sequence[float]]) -> list[int]:
        import numpy as np

        assert self._model is not None
        pred = self._model.predict(np.asarray(x, dtype=float))
        return [int(p) for p in pred]

    def predict_proba(self, x: Sequence[Sequence[float]]) -> list[tuple[float, float, float]]:
        import numpy as np

        assert self._model is not None
        proba = self._model.predict_proba(np.asarray(x, dtype=float))
        return [_pad_proba(row) for row in proba]

    def save_bytes(self) -> bytes:
        return b"LGB1" + pickle.dumps(self._model, protocol=4)

    @classmethod
    def load_bytes(cls, data: bytes) -> _LightGBMModel:
        if not data.startswith(b"LGB1"):
            raise ValueError("invalid lightgbm artifact")
        m = cls(ResourceLimits(1, 20, 3, 20, 2000, ("lightgbm",)))
        m._model = _load_trusted_pickle(data[4:])
        return m


class _XGBoostModel(BaseModel):
    algorithm = "xgboost"

    def __init__(self, limits: ResourceLimits) -> None:
        self._limits = limits
        self._model: Any = None

    def fit(
        self,
        x: Sequence[Sequence[float]],
        y: Sequence[int],
        *,
        feature_names: Sequence[str],
    ) -> None:
        import numpy as np
        from xgboost import XGBClassifier

        arr = np.asarray(x, dtype=float)
        labels = np.asarray(y, dtype=int)
        self._model = XGBClassifier(
            n_estimators=self._limits.max_trees,
            max_depth=self._limits.max_depth,
            n_jobs=self._limits.max_threads,
            verbosity=0,
            use_label_encoder=False,
            eval_metric="mlogloss",
        )
        self._model.fit(arr, labels)

    def predict(self, x: Sequence[Sequence[float]]) -> list[int]:
        import numpy as np

        assert self._model is not None
        pred = self._model.predict(np.asarray(x, dtype=float))
        return [int(p) for p in pred]

    def predict_proba(self, x: Sequence[Sequence[float]]) -> list[tuple[float, float, float]]:
        import numpy as np

        assert self._model is not None
        proba = self._model.predict_proba(np.asarray(x, dtype=float))
        return [_pad_proba(row) for row in proba]

    def save_bytes(self) -> bytes:
        import pickle

        return b"XGB1" + pickle.dumps(self._model, protocol=4)

    @classmethod
    def load_bytes(cls, data: bytes) -> _XGBoostModel:
        if not data.startswith(b"XGB1"):
            raise ValueError("invalid xgboost artifact")
        m = cls(ResourceLimits(1, 20, 3, 20, 2000, ("xgboost",)))
        m._model = _load_trusted_pickle(data[4:])
        return m


class _RandomForestModel(BaseModel):
    algorithm = "random_forest"

    def __init__(self, limits: ResourceLimits) -> None:
        self._limits = limits
        self._model: Any = None

    def fit(
        self,
        x: Sequence[Sequence[float]],
        y: Sequence[int],
        *,
        feature_names: Sequence[str],
    ) -> None:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier

        arr = np.asarray(x, dtype=float)
        labels = np.asarray(y, dtype=int)
        self._model = RandomForestClassifier(
            n_estimators=min(self._limits.max_trees, 100),
            max_depth=self._limits.max_depth,
            n_jobs=self._limits.max_threads,
            random_state=42,
        )
        self._model.fit(arr, labels)

    def predict(self, x: Sequence[Sequence[float]]) -> list[int]:
        import numpy as np

        assert self._model is not None
        pred = self._model.predict(np.asarray(x, dtype=float))
        return [int(p) for p in pred]

    def predict_proba(self, x: Sequence[Sequence[float]]) -> list[tuple[float, float, float]]:
        import numpy as np

        assert self._model is not None
        proba = self._model.predict_proba(np.asarray(x, dtype=float))
        classes = list(getattr(self._model, "classes_", [0, 1, 2]))
        out: list[tuple[float, float, float]] = []
        for row in proba:
            padded = [0.0, 0.0, 0.0]
            for c, p in zip(classes, row, strict=False):
                padded[int(c)] = float(p)
            total = sum(padded) or 1.0
            out.append((padded[0] / total, padded[1] / total, padded[2] / total))
        return out

    def save_bytes(self) -> bytes:
        import pickle

        return b"RF01" + pickle.dumps(self._model, protocol=4)

    @classmethod
    def load_bytes(cls, data: bytes) -> _RandomForestModel:
        if not data.startswith(b"RF01"):
            raise ValueError("invalid random_forest artifact")
        m = cls(ResourceLimits(1, 20, 3, 20, 2000, ("random_forest",)))
        m._model = _load_trusted_pickle(data[4:])
        return m


class _CatBoostModel(BaseModel):
    algorithm = "catboost"

    def __init__(self, limits: ResourceLimits) -> None:
        self._limits = limits
        self._model: Any = None

    def fit(
        self,
        x: Sequence[Sequence[float]],
        y: Sequence[int],
        *,
        feature_names: Sequence[str],
    ) -> None:
        from catboost import CatBoostClassifier

        self._model = CatBoostClassifier(
            iterations=min(self._limits.max_trees, 100),
            depth=min(self._limits.max_depth, 6),
            thread_count=self._limits.max_threads,
            verbose=False,
            allow_writing_files=False,
        )
        self._model.fit(list(x), list(y))

    def predict(self, x: Sequence[Sequence[float]]) -> list[int]:
        assert self._model is not None
        pred = self._model.predict(list(x))
        return [int(p[0] if isinstance(p, (list, tuple)) else p) for p in pred]

    def predict_proba(self, x: Sequence[Sequence[float]]) -> list[tuple[float, float, float]]:
        assert self._model is not None
        proba = self._model.predict_proba(list(x))
        return [_pad_proba(row) for row in proba]

    def save_bytes(self) -> bytes:
        import pickle

        return b"CB01" + pickle.dumps(self._model, protocol=4)

    @classmethod
    def load_bytes(cls, data: bytes) -> _CatBoostModel:
        if not data.startswith(b"CB01"):
            raise ValueError("invalid catboost artifact")
        m = cls(ResourceLimits(1, 20, 3, 20, 2000, ("catboost",)))
        m._model = _load_trusted_pickle(data[4:])
        return m


def load_model_bytes(algorithm: str, data: bytes, *, trusted: bool = False) -> BaseModel:
    if not trusted:
        raise ValueError("untrusted model artifacts are rejected")
    algo = algorithm.lower()
    if algo == "fallback":
        return FallbackModel.load_bytes(data)
    if algo == "lightgbm":
        return _LightGBMModel.load_bytes(data)
    if algo == "xgboost":
        return _XGBoostModel.load_bytes(data)
    if algo == "random_forest":
        return _RandomForestModel.load_bytes(data)
    if algo == "catboost":
        return _CatBoostModel.load_bytes(data)
    raise ValueError(f"unknown algorithm: {algorithm}")
