"""Strongly typed application configuration.

Secrets (API keys/secrets) are NEVER stored inside these models.
They live exclusively in a CredentialStore.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from crypto.core.types import HardwareProfile

# Schema version for forward compatibility. Bump when the on-disk shape changes
# in a non-backward-compatible way.
SCHEMA_VERSION: int = 1


class ConfigError(ValueError):
    """Raised when configuration is invalid or cannot be loaded."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Process-level runtime preferences (non-secret)."""

    data_dir: str = ""  # empty → platform default (%LOCALAPPDATA%\\CRYPTO)
    log_level: str = "INFO"
    paper_trading: bool = True
    read_only: bool = False

    def validate(self) -> None:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in allowed:
            raise ConfigError(f"log_level must be one of {sorted(allowed)}")


@dataclass(frozen=True, slots=True)
class ExchangeConfig:
    """Which exchange/account the bot should use (identifiers only).

    Actual API credentials are looked up from CredentialStore using
    (exchange_id, account_id).
    """

    exchange_id: str = ""
    account_id: str = "default"
    # Future: sandbox / testnet flag, rate-limit overrides, etc.

    def validate(self) -> None:
        if self.exchange_id and not _is_safe_identifier(self.exchange_id):
            raise ConfigError(
                "exchange_id must be a non-empty alphanumeric identifier "
                "(letters, digits, underscore, hyphen)"
            )
        if not _is_safe_identifier(self.account_id):
            raise ConfigError(
                "account_id must be a non-empty alphanumeric identifier "
                "(letters, digits, underscore, hyphen)"
            )


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Risk policy. These limits are NEVER altered by hardware profile."""

    max_position_pct: float = 5.0  # % of equity per position
    max_total_exposure_pct: float = 25.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0
    max_open_positions: int = 5
    kill_switch_enabled: bool = True

    def validate(self) -> None:
        if not (0.0 < self.max_position_pct <= 100.0):
            raise ConfigError("max_position_pct must be in (0, 100]")
        if not (0.0 < self.max_total_exposure_pct <= 100.0):
            raise ConfigError("max_total_exposure_pct must be in (0, 100]")
        if not (0.0 < self.max_daily_loss_pct <= 100.0):
            raise ConfigError("max_daily_loss_pct must be in (0, 100]")
        if not (0.0 < self.max_drawdown_pct <= 100.0):
            raise ConfigError("max_drawdown_pct must be in (0, 100]")
        if self.max_open_positions < 0:
            raise ConfigError("max_open_positions must be >= 0")


@dataclass(frozen=True, slots=True)
class HardwareConfig:
    """Preferred hardware/ML profile (hint; runtime detection may override)."""

    preferred_profile: str = "BALANCED"
    # Future: force_profile, allow_gpu, etc.

    def validate(self) -> None:
        try:
            HardwareProfile[self.preferred_profile]
        except KeyError as exc:
            names = [p.name for p in HardwareProfile]
            raise ConfigError(f"preferred_profile must be one of {names}") from exc


@dataclass(frozen=True, slots=True)
class MLConfig:
    """ML runtime preferences (non-secret, non-training)."""

    inference_enabled: bool = True
    # Future: model_registry_path, canary_pct, etc.

    def validate(self) -> None:
        pass  # nothing to validate yet


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Top-level application configuration.

    Never contains API keys or secrets.
    """

    schema_version: int = SCHEMA_VERSION
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    ml: MLConfig = field(default_factory=MLConfig)

    def validate(self) -> None:
        if self.schema_version < 1:
            raise ConfigError("schema_version must be >= 1")
        self.runtime.validate()
        self.exchange.validate()
        self.risk.validate()
        self.hardware.validate()
        self.ml.validate()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON/TOML (no secrets)."""
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppConfig:
        """Deserialize and validate. Unknown top-level keys are ignored for
        forward compatibility; nested unknown keys raise on strict construction
        via dataclass.
        """
        if not isinstance(data, Mapping):
            raise ConfigError("configuration root must be a mapping")

        schema_version = int(data.get("schema_version", SCHEMA_VERSION))

        runtime = _build_section(RuntimeConfig, data.get("runtime"))
        exchange = _build_section(ExchangeConfig, data.get("exchange"))
        risk = _build_section(RiskConfig, data.get("risk"))
        hardware = _build_section(HardwareConfig, data.get("hardware"))
        ml = _build_section(MLConfig, data.get("ml"))

        cfg = cls(
            schema_version=schema_version,
            runtime=runtime,
            exchange=exchange,
            risk=risk,
            hardware=hardware,
            ml=ml,
        )
        cfg.validate()
        return cfg

    @classmethod
    def from_json(cls, text: str) -> AppConfig:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid JSON: {exc}") from exc
        return cls.from_dict(data)

    @classmethod
    def load(cls, path: str | Path) -> AppConfig:
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"configuration file not found: {p}")
        return cls.from_json(p.read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> None:
        """Write non-secret configuration to disk."""
        self.validate()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json() + "\n", encoding="utf-8")

    @classmethod
    def default(cls) -> AppConfig:
        """Return a validated default configuration."""
        cfg = cls()
        cfg.validate()
        return cfg


def _build_section(cls: type[Any], raw: Any) -> Any:
    if raw is None:
        return cls()
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{cls.__name__} section must be a mapping")
    # Only pass known fields; ignore unknown keys for forward compatibility.
    known = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {k: v for k, v in raw.items() if k in known}
    try:
        return cls(**filtered)
    except TypeError as exc:
        raise ConfigError(f"invalid {cls.__name__}: {exc}") from exc


def _is_safe_identifier(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    if value != value.strip():
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    return all(c in allowed for c in value)
