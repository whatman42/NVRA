"""Provider selection policy with mandatory local fallback."""
from __future__ import annotations

from typing import Optional

from .base import ComputeProvider
from .colab import ColabComputeProvider
from .config import ComputeConfig, load_compute_config
from .kaggle import KaggleComputeProvider
from .local import LocalComputeProvider
from .types import ProviderStatus


def select_provider(
    config: Optional[ComputeConfig] = None,
    *,
    local: Optional[LocalComputeProvider] = None,
    colab: Optional[ColabComputeProvider] = None,
    kaggle: Optional[KaggleComputeProvider] = None,
) -> ComputeProvider:
    """Choose a provider per policy. Cloud unavailability never fails NVRA — falls back to local."""
    cfg = config or load_compute_config()
    local_p = local or LocalComputeProvider()
    colab_p = colab or ColabComputeProvider(
        enabled=cfg.colab.enabled, opportunistic=cfg.colab.opportunistic
    )
    kaggle_p = kaggle or KaggleComputeProvider(
        enabled=cfg.kaggle.enabled, opportunistic=cfg.kaggle.opportunistic
    )

    mode = cfg.provider

    if mode == "local":
        return local_p

    if mode == "colab":
        if colab_p.probe().status == ProviderStatus.AVAILABLE:
            return colab_p
        return local_p

    if mode == "kaggle":
        if kaggle_p.probe().status == ProviderStatus.AVAILABLE:
            return kaggle_p
        return local_p

    # auto: local baseline; cloud only if explicitly enabled AND available
    if cfg.colab.enabled and colab_p.probe().status == ProviderStatus.AVAILABLE:
        return colab_p
    if cfg.kaggle.enabled and kaggle_p.probe().status == ProviderStatus.AVAILABLE:
        return kaggle_p
    return local_p
