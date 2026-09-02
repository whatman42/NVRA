"""Durable non-secret first-run setup state.

Never stores passwords, API keys, tokens, or private keys.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SETUP_SCHEMA_VERSION = "1.0"

# Forbidden key fragments — must never appear in persisted setup state
_FORBIDDEN = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api_secret",
    "private_key",
    "credential",
    "kaggle",
    "oauth",
)


@dataclass
class FirstRunSetupState:
    setup_completed: bool = False
    setup_version: str = SETUP_SCHEMA_VERSION
    schema_version: str = SETUP_SCHEMA_VERSION
    workload_profile: str = "LOW_END_8GB"
    execution_mode: str = "PAPER"
    exchange_id: str = ""
    operator_configured: bool = False
    telegram_configured: bool = False
    telegram_skipped: bool = False
    local_compute_enabled: bool = True
    colab_enabled: bool = False
    kaggle_enabled: bool = False
    compute_provider: str = "auto"
    configured_providers: tuple[str, ...] = ("local",)
    data_dir: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["configured_providers"] = list(self.configured_providers)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FirstRunSetupState":
        providers = data.get("configured_providers") or ("local",)
        return cls(
            setup_completed=bool(data.get("setup_completed", False)),
            setup_version=str(data.get("setup_version") or SETUP_SCHEMA_VERSION),
            schema_version=str(data.get("schema_version") or SETUP_SCHEMA_VERSION),
            workload_profile=str(data.get("workload_profile") or "LOW_END_8GB"),
            execution_mode=str(data.get("execution_mode") or "PAPER"),
            exchange_id=str(data.get("exchange_id") or ""),
            operator_configured=bool(data.get("operator_configured", False)),
            telegram_configured=bool(data.get("telegram_configured", False)),
            telegram_skipped=bool(data.get("telegram_skipped", False)),
            local_compute_enabled=bool(data.get("local_compute_enabled", True)),
            colab_enabled=bool(data.get("colab_enabled", False)),
            kaggle_enabled=bool(data.get("kaggle_enabled", False)),
            compute_provider=str(data.get("compute_provider") or "auto"),
            configured_providers=tuple(providers),
            data_dir=str(data.get("data_dir") or ""),
            completed_at=str(data.get("completed_at") or ""),
        )


def _assert_no_secrets_in_payload(data: dict[str, Any]) -> None:
    for key in data:
        k = str(key).lower().replace("-", "_")
        for frag in _FORBIDDEN:
            # allow non-secret flags like kaggle_enabled / telegram_configured
            if frag in k and k not in {
                "kaggle_enabled",
                "telegram_configured",
                "telegram_skipped",
                "operator_configured",
                "local_compute_enabled",
                "colab_enabled",
                "configured_providers",
            }:
                raise ValueError(f"forbidden key in setup state: {key}")


def setup_state_path(state_dir: Path) -> Path:
    return Path(state_dir) / "first_run_setup.json"


def load_setup_state(state_dir: Path) -> FirstRunSetupState:
    path = setup_state_path(state_dir)
    if not path.is_file():
        return FirstRunSetupState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return FirstRunSetupState()
    if not isinstance(data, dict):
        return FirstRunSetupState()
    return FirstRunSetupState.from_dict(data)


def save_setup_state(state_dir: Path, state: FirstRunSetupState) -> Path:
    path = setup_state_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = state.to_dict()
    _assert_no_secrets_in_payload(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    try:
        import os

        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
