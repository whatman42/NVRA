"""Provider selection policy with mandatory local fallback and workload awareness."""
from __future__ import annotations

from typing import Optional

from .base import ComputeProvider
from .colab import ColabComputeProvider
from .config import ComputeConfig, load_compute_config
from .kaggle import KaggleComputeProvider
from .local import LocalComputeProvider
from .types import ProviderStatus, TrainingJob, WorkloadType


def select_provider(
    config: Optional[ComputeConfig] = None,
    *,
    local: Optional[LocalComputeProvider] = None,
    colab: Optional[ColabComputeProvider] = None,
    kaggle: Optional[KaggleComputeProvider] = None,
    job: Optional[TrainingJob] = None,
) -> ComputeProvider:
    """Choose a provider per policy.

    Rules:
    - Cloud unavailability never fails NVRA — falls back to local.
    - Colab/Kaggle are only selected for HEAVY workloads when enabled+available.
    - Inference / light workloads always stay local.
    - Colab is never selected merely because a GPU exists remotely.
    """
    cfg = config or load_compute_config()
    local_p = local or LocalComputeProvider()
    colab_p = colab or ColabComputeProvider(
        enabled=cfg.colab.enabled, opportunistic=cfg.colab.opportunistic
    )
    kaggle_p = kaggle or KaggleComputeProvider(
        enabled=cfg.kaggle.enabled, opportunistic=cfg.kaggle.opportunistic
    )

    # Inference and light workloads are local-only (trusted path).
    if job is not None and not job.is_heavy():
        return local_p

    mode = cfg.provider

    if mode == "local":
        return local_p

    if mode == "colab":
        if job is not None and not job.is_heavy():
            return local_p
        if colab_p.probe().status == ProviderStatus.AVAILABLE:
            return colab_p
        return local_p

    if mode == "kaggle":
        if job is not None and not job.is_heavy():
            return local_p
        if kaggle_p.probe().status == ProviderStatus.AVAILABLE:
            return kaggle_p
        return local_p

    # auto: local baseline; cloud only for heavy + enabled + available
    if job is None or job.is_heavy():
        if cfg.colab.enabled and colab_p.probe().status == ProviderStatus.AVAILABLE:
            return colab_p
        if cfg.kaggle.enabled and kaggle_p.probe().status == ProviderStatus.AVAILABLE:
            return kaggle_p
    return local_p
