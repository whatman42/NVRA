"""Windows Credential Manager backend.

Uses the 'keyring' package when present. The package is optional and is
only required on Windows production builds.

This module is imported only on win32 (see create_credential_store).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from crypto.core.credentials import (
    CredentialBackendError,
    CredentialNotFoundError,
    CredentialStore,
    ExchangeCredentials,
    _validate_identifier,
)
from crypto.core.types import AccountId, ExchangeId, SecretStr

# Service name prefix used inside Windows Credential Manager.
_SERVICE_PREFIX = "CRYPTO"


def _service_name(exchange_id: str, account_id: str) -> str:
    return f"{_SERVICE_PREFIX}:{exchange_id}:{account_id}"


class WindowsCredentialStore(CredentialStore):
    """Stores credentials in Windows Credential Manager via keyring."""

    def __init__(self) -> None:
        try:
            import keyring
        except ImportError as exc:
            raise CredentialBackendError(
                "The 'keyring' package is required for Windows secure storage. "
                "Install it with: pip install keyring"
            ) from exc
        self._keyring = keyring
        # Quick health check
        try:
            self._keyring.get_keyring()
        except Exception as exc:  # noqa: BLE001
            raise CredentialBackendError(
                "Windows Credential Manager backend could not be initialised"
            ) from exc

    def set(self, credentials: ExchangeCredentials) -> None:
        credentials.validate()
        service = _service_name(credentials.exchange_id, credentials.account_id)
        # Store both key and secret as a single JSON blob under the username
        # so that list_accounts can later be approximated if needed.
        payload = {
            "api_key": credentials.api_key.get_secret_value(),
            "api_secret": credentials.api_secret.get_secret_value(),
        }
        try:
            self._keyring.set_password(
                service,
                credentials.account_id,
                json.dumps(payload),
            )
        except Exception as exc:  # noqa: BLE001
            raise CredentialBackendError("failed to store credentials securely") from exc

    def get(
        self, exchange_id: ExchangeId, account_id: AccountId = "default"
    ) -> ExchangeCredentials:
        _validate_identifier(exchange_id, "exchange_id")
        _validate_identifier(account_id, "account_id")
        service = _service_name(exchange_id, account_id)
        try:
            raw = self._keyring.get_password(service, account_id)
        except Exception as exc:  # noqa: BLE001
            raise CredentialBackendError("failed to read credentials") from exc
        if raw is None:
            raise CredentialNotFoundError(
                f"no credentials for exchange={exchange_id!r} account={account_id!r}"
            )
        try:
            data = json.loads(raw)
            return ExchangeCredentials(
                exchange_id=exchange_id,
                account_id=account_id,
                api_key=SecretStr(data["api_key"]),
                api_secret=SecretStr(data["api_secret"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise CredentialBackendError("stored credential payload is corrupt") from exc

    def delete(self, exchange_id: ExchangeId, account_id: AccountId = "default") -> bool:
        _validate_identifier(exchange_id, "exchange_id")
        _validate_identifier(account_id, "account_id")
        service = _service_name(exchange_id, account_id)
        try:
            existing = self._keyring.get_password(service, account_id)
            if existing is None:
                return False
            self._keyring.delete_password(service, account_id)
            return True
        except Exception as exc:  # noqa: BLE001
            raise CredentialBackendError("failed to delete credentials") from exc

    def exists(self, exchange_id: ExchangeId, account_id: AccountId = "default") -> bool:
        _validate_identifier(exchange_id, "exchange_id")
        _validate_identifier(account_id, "account_id")
        service = _service_name(exchange_id, account_id)
        try:
            return self._keyring.get_password(service, account_id) is not None
        except Exception as exc:  # noqa: BLE001
            raise CredentialBackendError("failed to query credentials") from exc

    def list_accounts(
        self, exchange_id: ExchangeId | None = None
    ) -> Sequence[tuple[ExchangeId, AccountId]]:
        # keyring's cross-platform API does not provide a portable list API.
        # Returning an empty sequence is the safe, documented behaviour.
        # A future Windows-specific enumeration can be added if required.
        return []
