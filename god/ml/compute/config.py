"""Backward-compatible compute provider configuration with safe defaults."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class ColabConfig:
    enabled: bool = False
    opportunistic: bool = True


@dataclass
class KaggleConfig:
    enabled: bool = False
    opportunistic: bool = True


@dataclass
class LocalConfig:
    enabled: bool = True


@dataclass
class ComputeConfig:
    """Default: local-only. Cloud remains opt-in."""

    provider: str = "auto"  # local | colab | kaggle | auto
    local: LocalConfig = field(default_factory=LocalConfig)
    colab: ColabConfig = field(default_factory=ColabConfig)
    kaggle: KaggleConfig = field(default_factory=KaggleConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "local": {"enabled": self.local.enabled},
            "colab": {
                "enabled": self.colab.enabled,
                "opportunistic": self.colab.opportunistic,
            },
            "kaggle": {
                "enabled": self.kaggle.enabled,
                "opportunistic": self.kaggle.opportunistic,
            },
        }


def load_compute_config(raw: Mapping[str, Any] | None = None) -> ComputeConfig:
    """Parse optional compute section; missing section => safe local-only defaults."""
    if not raw:
        return ComputeConfig()
    section = raw.get("compute") if "compute" in raw else raw
    if not isinstance(section, Mapping):
        return ComputeConfig()
    provider = str(section.get("provider") or "auto").strip().lower()
    if provider not in {"local", "colab", "kaggle", "auto"}:
        provider = "auto"

    local_raw = section.get("local") if isinstance(section.get("local"), Mapping) else {}
    colab_raw = section.get("colab") if isinstance(section.get("colab"), Mapping) else {}
    kaggle_raw = section.get("kaggle") if isinstance(section.get("kaggle"), Mapping) else {}

    return ComputeConfig(
        provider=provider,
        local=LocalConfig(enabled=bool(local_raw.get("enabled", True))),
        colab=ColabConfig(
            enabled=bool(colab_raw.get("enabled", False)),
            opportunistic=bool(colab_raw.get("opportunistic", True)),
        ),
        kaggle=KaggleConfig(
            enabled=bool(kaggle_raw.get("enabled", False)),
            opportunistic=bool(kaggle_raw.get("opportunistic", True)),
        ),
    )
