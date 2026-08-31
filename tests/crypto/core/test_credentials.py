"""Tests for CredentialStore and secret handling (Phase 1)."""

from __future__ import annotations

import logging
import sys

import pytest

from crypto.core.config import AppConfig
from crypto.core.credentials import (
    CredentialBackendError,
    CredentialNotFoundError,
    CredentialValidationError,
    ExchangeCredentials,
    InMemoryCredentialStore,
    create_credential_store,
)
from crypto.core.types import SecretStr


def _make_creds(
    exchange: str = "binance",
    account: str = "default",
    key: str = "test_api_key_12345678",
    secret: str = "test_api_secret_abcdefgh",
) -> ExchangeCredentials:
    return ExchangeCredentials(
        exchange_id=exchange,
        account_id=account,
        api_key=SecretStr(key),
        api_secret=SecretStr(secret),
    )


# ---------------------------------------------------------------------------
# SecretStr
# ---------------------------------------------------------------------------


def test_secret_str_redacts_repr_and_str() -> None:
    s = SecretStr("super-secret-value-xyz")
    assert str(s) == "********"
    assert "super-secret" not in repr(s)
    assert "********" in repr(s)
    assert s.get_secret_value() == "super-secret-value-xyz"


def test_secret_str_equality() -> None:
    a = SecretStr("abc")
    b = SecretStr("abc")
    c = SecretStr("xyz")
    assert a == b
    assert a != c


def test_secret_str_rejects_non_str() -> None:
    with pytest.raises(TypeError):
        SecretStr(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def test_reject_empty_key() -> None:
    with pytest.raises(CredentialValidationError, match="api_key"):
        _make_creds(key="").validate()


def test_reject_whitespace_only_secret() -> None:
    with pytest.raises(CredentialValidationError, match="api_secret"):
        _make_creds(secret="   ").validate()


def test_reject_leading_trailing_whitespace() -> None:
    with pytest.raises(CredentialValidationError):
        _make_creds(key="  padded_key_value  ").validate()


def test_reject_too_short() -> None:
    with pytest.raises(CredentialValidationError, match="too short"):
        _make_creds(key="short").validate()


def test_reject_invalid_exchange_id() -> None:
    with pytest.raises(CredentialValidationError, match="exchange_id"):
        _make_creds(exchange="binance!").validate()


def test_reject_empty_account_id() -> None:
    with pytest.raises(CredentialValidationError, match="account_id"):
        _make_creds(account="").validate()


# ---------------------------------------------------------------------------
# InMemoryCredentialStore lifecycle
# ---------------------------------------------------------------------------


def test_set_get_exists_delete() -> None:
    store = InMemoryCredentialStore()
    creds = _make_creds()
    assert store.exists("binance") is False
    store.set(creds)
    assert store.exists("binance") is True
    got = store.get("binance")
    assert got.api_key.get_secret_value() == "test_api_key_12345678"
    assert got.api_secret.get_secret_value() == "test_api_secret_abcdefgh"
    assert store.delete("binance") is True
    assert store.exists("binance") is False
    assert store.delete("binance") is False


def test_get_missing_raises() -> None:
    store = InMemoryCredentialStore()
    with pytest.raises(CredentialNotFoundError, match="no credentials"):
        store.get("binance")


def test_overwrite() -> None:
    store = InMemoryCredentialStore()
    store.set(_make_creds(key="first_key_value_xx"))
    store.set(_make_creds(key="second_key_value_yy"))
    got = store.get("binance")
    assert got.api_key.get_secret_value() == "second_key_value_yy"


def test_multiple_exchanges_and_accounts() -> None:
    store = InMemoryCredentialStore()
    store.set(_make_creds("binance", "main", key="binance_main_key_01"))
    store.set(_make_creds("binance", "sub", key="binance_sub_key_02"))
    store.set(_make_creds("indodax", "default", key="indodax_def_key_03"))

    assert store.exists("binance", "main")
    assert store.exists("binance", "sub")
    assert store.exists("indodax")
    assert not store.exists("tokocrypto")

    accounts = store.list_accounts()
    assert ("binance", "main") in accounts
    assert ("binance", "sub") in accounts
    assert ("indodax", "default") in accounts

    binance_only = store.list_accounts("binance")
    assert len(binance_only) == 2


# ---------------------------------------------------------------------------
# Secrets must not leak
# ---------------------------------------------------------------------------


def test_credentials_repr_redacts_secrets() -> None:
    creds = _make_creds()
    text = repr(creds)
    assert "test_api_key_12345678" not in text
    assert "test_api_secret_abcdefgh" not in text
    assert "********" in text


def test_exception_message_has_no_secret() -> None:
    store = InMemoryCredentialStore()
    try:
        store.get("binance")
    except CredentialNotFoundError as exc:
        msg = str(exc)
        assert "test_api" not in msg
        assert "secret" not in msg.lower() or "no credentials" in msg.lower()


def test_config_serialization_never_contains_secrets() -> None:
    # Even if a caller mistakenly puts a SecretStr somewhere, AppConfig
    # itself has no secret fields.
    cfg = AppConfig.default()
    blob = cfg.to_json().lower()
    assert "api_key" not in blob
    assert "api_secret" not in blob
    assert "password" not in blob


def test_logging_does_not_emit_secret(caplog: pytest.LogCaptureFixture) -> None:
    secret = SecretStr("should_never_appear_in_logs_xyz")
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("crypto.test").info("credential object: %s", secret)
        logging.getLogger("crypto.test").debug("repr=%r", secret)
    combined = " ".join(r.message for r in caplog.records)
    assert "should_never_appear_in_logs_xyz" not in combined
    assert "********" in combined


# ---------------------------------------------------------------------------
# Factory / platform selection
# ---------------------------------------------------------------------------


def test_factory_in_memory_on_request() -> None:
    store = create_credential_store(allow_in_memory=True)
    assert isinstance(store, InMemoryCredentialStore)


def test_factory_fails_closed_on_linux_without_flag() -> None:
    if sys.platform == "win32":
        pytest.skip("Windows path uses secure backend")
    with pytest.raises(CredentialBackendError, match="No secure credential backend"):
        create_credential_store(allow_in_memory=False)


def test_windows_backend_module_importable() -> None:
    # The module must be importable on any platform; the class only activates
    # when keyring is present and we are on win32.
    from crypto.core import windows_cred

    assert hasattr(windows_cred, "WindowsCredentialStore")
