"""Secure credential storage abstraction.

API keys and secrets live ONLY inside a CredentialStore implementation.
They never appear in AppConfig, logs, exception messages, or serialized files.
"""

from __future__ import annotations

import re
import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from crypto.core.types import AccountId, ExchangeId, SecretStr

# Reasonable bounds for exchange API credentials (structure only).
_MIN_KEY_LEN = 8
_MAX_KEY_LEN = 256
_MIN_SECRET_LEN = 8
_MAX_SECRET_LEN = 512

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class CredentialError(Exception):
    """Base class for credential-related errors.

    Message must never contain the secret value itself.
    """


class CredentialValidationError(CredentialError):
    """Raised when a credential fails structural validation."""


class CredentialNotFoundError(CredentialError):
    """Raised when a requested credential does not exist."""


class CredentialBackendError(CredentialError):
    """Raised when the underlying secure storage backend fails."""


@dataclass(frozen=True, slots=True)
class ExchangeCredentials:
    """A single set of exchange API credentials.

    The secret fields are SecretStr so that repr/str never leak them.
    """

    exchange_id: ExchangeId
    account_id: AccountId
    api_key: SecretStr
    api_secret: SecretStr

    def validate(self) -> None:
        _validate_identifier(self.exchange_id, "exchange_id")
        _validate_identifier(self.account_id, "account_id")
        _validate_secret_field(self.api_key, "api_key", _MIN_KEY_LEN, _MAX_KEY_LEN)
        _validate_secret_field(self.api_secret, "api_secret", _MIN_SECRET_LEN, _MAX_SECRET_LEN)


def _validate_identifier(value: str, field_name: str) -> None:
    if not value or not isinstance(value, str):
        raise CredentialValidationError(f"{field_name} must be a non-empty string")
    if value != value.strip():
        raise CredentialValidationError(f"{field_name} must not have leading/trailing whitespace")
    if not _SAFE_ID_RE.match(value):
        raise CredentialValidationError(
            f"{field_name} may only contain letters, digits, underscore, hyphen"
        )


def _validate_secret_field(secret: SecretStr, field_name: str, min_len: int, max_len: int) -> None:
    if not isinstance(secret, SecretStr):
        raise CredentialValidationError(f"{field_name} must be a SecretStr")
    raw = secret.get_secret_value()
    if not raw or not raw.strip():
        raise CredentialValidationError(f"{field_name} must not be empty or whitespace-only")
    if raw != raw.strip():
        raise CredentialValidationError(f"{field_name} must not have leading/trailing whitespace")
    if len(raw) < min_len:
        raise CredentialValidationError(f"{field_name} is too short (minimum {min_len} characters)")
    if len(raw) > max_len:
        raise CredentialValidationError(f"{field_name} is too long (maximum {max_len} characters)")


class CredentialStore(ABC):
    """Abstract secure store for exchange API credentials.

    Implementations must:
    - never write secrets to ordinary files or logs;
    - redact secrets in any string representation;
    - fail closed if the secure backend is unavailable.
    """

    @abstractmethod
    def set(self, credentials: ExchangeCredentials) -> None:
        """Store or overwrite credentials. Validates structure first."""

    @abstractmethod
    def get(
        self, exchange_id: ExchangeId, account_id: AccountId = "default"
    ) -> ExchangeCredentials:
        """Retrieve credentials. Raises CredentialNotFoundError if missing."""

    @abstractmethod
    def delete(self, exchange_id: ExchangeId, account_id: AccountId = "default") -> bool:
        """Delete credentials. Returns True if they existed, False otherwise."""

    @abstractmethod
    def exists(self, exchange_id: ExchangeId, account_id: AccountId = "default") -> bool:
        """Return True if credentials are present."""

    @abstractmethod
    def list_accounts(
        self, exchange_id: ExchangeId | None = None
    ) -> Sequence[tuple[ExchangeId, AccountId]]:
        """List known (exchange_id, account_id) pairs. Optionally filter by exchange."""


class InMemoryCredentialStore(CredentialStore):
    """Ephemeral credential store for tests and non-production use.

    Secrets live only in process memory. They are never written to disk.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], ExchangeCredentials] = {}

    def set(self, credentials: ExchangeCredentials) -> None:
        credentials.validate()
        key = (credentials.exchange_id, credentials.account_id)
        self._store[key] = credentials

    def get(
        self, exchange_id: ExchangeId, account_id: AccountId = "default"
    ) -> ExchangeCredentials:
        _validate_identifier(exchange_id, "exchange_id")
        _validate_identifier(account_id, "account_id")
        key = (exchange_id, account_id)
        try:
            return self._store[key]
        except KeyError as exc:
            raise CredentialNotFoundError(
                f"no credentials for exchange={exchange_id!r} account={account_id!r}"
            ) from exc

    def delete(self, exchange_id: ExchangeId, account_id: AccountId = "default") -> bool:
        _validate_identifier(exchange_id, "exchange_id")
        _validate_identifier(account_id, "account_id")
        key = (exchange_id, account_id)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def exists(self, exchange_id: ExchangeId, account_id: AccountId = "default") -> bool:
        _validate_identifier(exchange_id, "exchange_id")
        _validate_identifier(account_id, "account_id")
        return (exchange_id, account_id) in self._store

    def list_accounts(
        self, exchange_id: ExchangeId | None = None
    ) -> Sequence[tuple[ExchangeId, AccountId]]:
        if exchange_id is not None:
            _validate_identifier(exchange_id, "exchange_id")
            return [(e, a) for (e, a) in self._store if e == exchange_id]
        return list(self._store.keys())


def create_credential_store(*, allow_in_memory: bool = False) -> CredentialStore:
    """Factory that selects the appropriate backend.

    Production (Windows):
        Uses Windows Credential Manager via the optional 'keyring' package
        when available. Fails closed if the secure backend cannot be used.

    Non-Windows / CI:
        Returns InMemoryCredentialStore only when allow_in_memory=True.
        Otherwise raises CredentialBackendError so that secrets are never
        stored insecurely by accident.

    Environment variables are intentionally NOT used as a production store.
    """
    if sys.platform == "win32":
        try:
            from crypto.core.windows_cred import WindowsCredentialStore

            return WindowsCredentialStore()
        except Exception as exc:  # noqa: BLE001 — fail closed
            raise CredentialBackendError(
                "Windows secure credential backend is unavailable. "
                "Install the optional 'keyring' package or ensure "
                "Windows Credential Manager is accessible. "
                "Refusing to fall back to plaintext storage."
            ) from exc

    if allow_in_memory:
        return InMemoryCredentialStore()

    raise CredentialBackendError(
        "No secure credential backend available on this platform. "
        "For tests and development, pass allow_in_memory=True. "
        "Production Windows builds must use the OS credential store."
    )
