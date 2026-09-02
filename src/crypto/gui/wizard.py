"""First-run wizard data model — secrets go to CredentialStore only.

Logical order:
  WELCOME → HARDWARE → OPERATOR → DATA → EXCHANGE → TELEGRAM →
  COMPUTE → SECURITY → VALIDATE → DONE

Secrets are held only transiently in memory and cleared after CredentialStore write.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from crypto.execution.models import ExecutionMode


class WizardStep(Enum):
    WELCOME = auto()
    HARDWARE = auto()
    OPERATOR = auto()
    DATA = auto()
    EXCHANGE = auto()
    CREDENTIALS = auto()
    TELEGRAM = auto()
    COMPUTE = auto()
    SECURITY = auto()
    VALIDATE = auto()
    DONE = auto()


WIZARD_ORDER: tuple[WizardStep, ...] = (
    WizardStep.WELCOME,
    WizardStep.HARDWARE,
    WizardStep.OPERATOR,
    WizardStep.DATA,
    WizardStep.EXCHANGE,
    WizardStep.CREDENTIALS,
    WizardStep.TELEGRAM,
    WizardStep.COMPUTE,
    WizardStep.SECURITY,
    WizardStep.VALIDATE,
    WizardStep.DONE,
)

OPTIONAL_STEPS = frozenset({WizardStep.TELEGRAM, WizardStep.COMPUTE})

SUPPORTED_EXCHANGES: tuple[str, ...] = (
    "binance",
    "tokocrypto",
    "indodax",
    "mt5",
)


@dataclass
class HardwareSummary:
    profile: str = "LOW_END_8GB"
    total_ram_mb: int = 0
    cpu_threads: int = 0
    gpu_available: bool = False
    notes: tuple[str, ...] = ()


@dataclass
class SecurityCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class WizardState:
    step: WizardStep = WizardStep.WELCOME
    version_label: str = "NVRA"
    os_name: str = ""
    data_dir: str = ""
    state_dir: str = ""
    config_dir: str = ""
    hardware: HardwareSummary = field(default_factory=HardwareSummary)
    operator_username: str = ""
    symbols: str = ""
    timeframe: str = "1h"
    data_cache_dir: str = ""
    exchange_id: str = ""
    _api_key: str = ""
    _api_secret: str = ""
    _telegram_token: str = ""
    _operator_password: str = ""
    _kaggle_token: str = ""
    telegram_chat_id: str = ""
    telegram_skipped: bool = False
    mode: ExecutionMode = ExecutionMode.PAPER
    compute_provider: str = "auto"
    local_compute_enabled: bool = True
    colab_enabled: bool = False
    kaggle_enabled: bool = False
    colab_status: str = "DISABLED"
    kaggle_status: str = "DISABLED"
    connection_ok: bool = False
    withdrawal_warning: bool = False
    security_checks: list[SecurityCheck] = field(default_factory=list)
    validation_ok: bool = False
    setup_completed: bool = False

    def set_api_key(self, value: str) -> None:
        self._api_key = value

    def set_api_secret(self, value: str) -> None:
        self._api_secret = value

    def set_telegram_token(self, value: str) -> None:
        self._telegram_token = value

    def set_operator_password(self, value: str) -> None:
        self._operator_password = value

    def set_kaggle_token(self, value: str) -> None:
        self._kaggle_token = value

    def take_secrets(self) -> dict[str, str]:
        out = {
            "api_key": self._api_key,
            "api_secret": self._api_secret,
            "telegram_token": self._telegram_token,
            "operator_password": self._operator_password,
            "kaggle_token": self._kaggle_token,
        }
        self._api_key = ""
        self._api_secret = ""
        self._telegram_token = ""
        self._operator_password = ""
        self._kaggle_token = ""
        return out

    def has_pending_secrets(self) -> bool:
        return bool(
            self._api_key
            or self._api_secret
            or self._telegram_token
            or self._operator_password
            or self._kaggle_token
        )

    def can_advance(self) -> tuple[bool, str]:
        s = self.step
        if s == WizardStep.OPERATOR:
            if not self.operator_username.strip():
                return False, "operator_username_required"
            if not self._operator_password:
                return False, "operator_password_required"
        if s == WizardStep.EXCHANGE:
            if self.exchange_id not in SUPPORTED_EXCHANGES:
                return False, "exchange_required"
        if s == WizardStep.CREDENTIALS:
            if self.mode != ExecutionMode.PAPER:
                if not self._api_key or not self._api_secret:
                    return False, "credentials_required_for_non_paper"
        if s == WizardStep.SECURITY:
            if any(not c.passed for c in self.security_checks):
                return False, "security_checks_failed"
        if s == WizardStep.VALIDATE:
            if not self.validation_ok:
                return False, "validation_incomplete"
        return True, ""

    def is_optional(self) -> bool:
        return self.step in OPTIONAL_STEPS

    def next_step(self) -> WizardStep:
        order = list(WIZARD_ORDER)
        try:
            i = order.index(self.step)
        except ValueError:
            return WizardStep.DONE
        if i + 1 >= len(order):
            return WizardStep.DONE
        return order[i + 1]

    def prev_step(self) -> WizardStep:
        order = list(WIZARD_ORDER)
        try:
            i = order.index(self.step)
        except ValueError:
            return WizardStep.WELCOME
        if i <= 0:
            return WizardStep.WELCOME
        return order[i - 1]

    def summary(self) -> dict[str, str]:
        return {
            "operator": "READY" if self.operator_username else "MISSING",
            "hardware": self.hardware.profile,
            "data": "READY" if self.data_dir else "MISSING",
            "broker": self.mode.name,
            "exchange": self.exchange_id or "none",
            "telegram": (
                "SKIPPED"
                if self.telegram_skipped
                else ("CONFIGURED" if self.telegram_chat_id else "NOT_CONFIGURED")
            ),
            "local_compute": "READY" if self.local_compute_enabled else "DISABLED",
            "colab": self.colab_status,
            "kaggle": self.kaggle_status,
            "security": (
                "PASS"
                if self.security_checks and all(c.passed for c in self.security_checks)
                else "PENDING"
            ),
            "validation": "PASS" if self.validation_ok else "PENDING",
            "runtime": "READY" if self.setup_completed else "SETUP",
            "execution_mode": "PAPER ONLY" if self.mode == ExecutionMode.PAPER else self.mode.name,
        }

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "step": self.step.name,
            "version_label": self.version_label,
            "os_name": self.os_name,
            "data_dir": self.data_dir,
            "state_dir": self.state_dir,
            "config_dir": self.config_dir,
            "hardware_profile": self.hardware.profile,
            "operator_username": self.operator_username,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "data_cache_dir": self.data_cache_dir,
            "exchange_id": self.exchange_id,
            "telegram_chat_id": self.telegram_chat_id,
            "telegram_skipped": self.telegram_skipped,
            "mode": self.mode.name,
            "compute_provider": self.compute_provider,
            "local_compute_enabled": self.local_compute_enabled,
            "colab_enabled": self.colab_enabled,
            "kaggle_enabled": self.kaggle_enabled,
            "colab_status": self.colab_status,
            "kaggle_status": self.kaggle_status,
            "connection_ok": self.connection_ok,
            "validation_ok": self.validation_ok,
            "setup_completed": self.setup_completed,
        }

    def __repr__(self) -> str:
        return (
            f"WizardState(step={self.step.name}, exchange={self.exchange_id}, "
            f"mode={self.mode.name}, secrets=***)"
        )

    def __str__(self) -> str:
        return repr(self)
