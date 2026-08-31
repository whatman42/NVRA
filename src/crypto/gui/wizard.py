"""First-run wizard data model — secrets go to CredentialStore only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from crypto.execution.models import ExecutionMode


class WizardStep(Enum):
    EXCHANGE = auto()
    CREDENTIALS = auto()
    TELEGRAM = auto()
    MODE = auto()
    VALIDATE = auto()
    DONE = auto()


@dataclass
class WizardState:
    step: WizardStep = WizardStep.EXCHANGE
    exchange_id: str = ""
    # secrets held only transiently in memory during setup — never logged
    _api_key: str = ""
    _api_secret: str = ""
    _telegram_token: str = ""
    telegram_chat_id: str = ""
    mode: ExecutionMode = ExecutionMode.PAPER
    connection_ok: bool = False
    withdrawal_warning: bool = False

    def set_api_key(self, value: str) -> None:
        self._api_key = value

    def set_api_secret(self, value: str) -> None:
        self._api_secret = value

    def set_telegram_token(self, value: str) -> None:
        self._telegram_token = value

    def take_secrets(self) -> dict[str, str]:
        """Return secrets once for CredentialStore write, then clear memory."""
        out = {
            "api_key": self._api_key,
            "api_secret": self._api_secret,
            "telegram_token": self._telegram_token,
        }
        self._api_key = ""
        self._api_secret = ""
        self._telegram_token = ""
        return out

    def __repr__(self) -> str:
        return (
            f"WizardState(step={self.step.name}, exchange={self.exchange_id}, "
            f"mode={self.mode.name}, secrets=***)"
        )

    def __str__(self) -> str:
        return repr(self)
