"""Tests for typed configuration (Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto.core.config import (
    SCHEMA_VERSION,
    AppConfig,
    ConfigError,
    ExchangeConfig,
    HardwareConfig,
    MLConfig,
    RiskConfig,
    RuntimeConfig,
)


def test_default_config_is_valid() -> None:
    cfg = AppConfig.default()
    assert cfg.schema_version == SCHEMA_VERSION
    assert cfg.runtime.paper_trading is True
    assert cfg.risk.kill_switch_enabled is True
    cfg.validate()  # must not raise


def test_serialization_roundtrip() -> None:
    original = AppConfig.default()
    text = original.to_json()
    restored = AppConfig.from_json(text)
    assert restored == original
    assert "api_key" not in text
    assert "api_secret" not in text
    assert "secret" not in text.lower()


def test_to_dict_contains_no_secrets() -> None:
    d = AppConfig.default().to_dict()
    flat = json.dumps(d).lower()
    assert "api_key" not in flat
    assert "api_secret" not in flat
    assert "password" not in flat


def test_from_dict_ignores_unknown_top_level_keys() -> None:
    data = AppConfig.default().to_dict()
    data["future_extension"] = {"foo": 1}
    cfg = AppConfig.from_dict(data)
    assert cfg.schema_version == SCHEMA_VERSION


def test_invalid_log_level() -> None:
    with pytest.raises(ConfigError, match="log_level"):
        RuntimeConfig(log_level="VERBOSE").validate()


def test_invalid_risk_bounds() -> None:
    with pytest.raises(ConfigError):
        RiskConfig(max_position_pct=0).validate()
    with pytest.raises(ConfigError):
        RiskConfig(max_position_pct=101).validate()
    with pytest.raises(ConfigError):
        RiskConfig(max_open_positions=-1).validate()


def test_invalid_hardware_profile() -> None:
    with pytest.raises(ConfigError, match="preferred_profile"):
        HardwareConfig(preferred_profile="TURBO").validate()


def test_exchange_identifier_validation() -> None:
    with pytest.raises(ConfigError):
        ExchangeConfig(exchange_id="binance!", account_id="default").validate()
    with pytest.raises(ConfigError):
        ExchangeConfig(exchange_id="binance", account_id="").validate()
    # empty exchange_id is allowed (not yet selected)
    ExchangeConfig(exchange_id="", account_id="default").validate()


def test_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    original = AppConfig(
        exchange=ExchangeConfig(exchange_id="binance", account_id="main"),
        risk=RiskConfig(max_position_pct=2.5),
    )
    original.save(path)
    loaded = AppConfig.load(path)
    assert loaded.exchange.exchange_id == "binance"
    assert loaded.risk.max_position_pct == 2.5
    # file content must not contain secrets
    content = path.read_text(encoding="utf-8").lower()
    assert "api_key" not in content
    assert "secret" not in content


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        AppConfig.load(tmp_path / "missing.json")


def test_invalid_json() -> None:
    with pytest.raises(ConfigError, match="invalid JSON"):
        AppConfig.from_json("{not json")


def test_schema_version_present() -> None:
    cfg = AppConfig.default()
    assert cfg.schema_version >= 1
    d = cfg.to_dict()
    assert d["schema_version"] == SCHEMA_VERSION


def test_sections_have_defaults() -> None:
    cfg = AppConfig()
    assert isinstance(cfg.runtime, RuntimeConfig)
    assert isinstance(cfg.exchange, ExchangeConfig)
    assert isinstance(cfg.risk, RiskConfig)
    assert isinstance(cfg.hardware, HardwareConfig)
    assert isinstance(cfg.ml, MLConfig)
