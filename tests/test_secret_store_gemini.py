"""SecretStore Gemini + Telegram/Crypto clear helpers — no plaintext config."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    # Force memory backend so tests don't depend on OS keyring
    from nvra_unified.secrets import SecretStore
    s = SecretStore()
    s._keyring = None
    s._memory = {}
    return s


def test_gemini_save_get_delete(store):
    assert store.gemini_api_key() is None or store.gemini_api_key() == ""
    assert store.gemini_configured() is False
    store.set_gemini_api_key("test-gemini-key-xyz")
    assert store.gemini_api_key() == "test-gemini-key-xyz"
    assert store.gemini_configured() is True
    store.delete_gemini_api_key()
    assert store.gemini_api_key() is None
    assert store.gemini_configured() is False


def test_gemini_env_fallback(store, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-only-key")
    assert store.gemini_api_key() == "env-only-key"
    store.set_gemini_api_key("keyring-wins")
    assert store.gemini_api_key() == "keyring-wins"
    store.delete_gemini_api_key()
    assert store.gemini_api_key() == "env-only-key"


def test_telegram_clear(store):
    store.set_telegram("tok", "123")
    assert store.telegram_configured() is True
    store.delete_telegram()
    assert store.telegram_configured() is False


def test_exchange_clear(store):
    store.set_exchange("binance", "default", "k", "s")
    assert store.exchange_configured("binance") is True
    store.delete_exchange("binance")
    assert store.exchange_configured("binance") is False


def test_no_secret_in_config_json(tmp_path, monkeypatch, store):
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    store.set_gemini_api_key("super-secret-gemini")
    store.set_telegram("tg-token-secret", "999")
    store.set_exchange("binance", "default", "api-key-secret", "api-secret-secret")
    from nvra_unified.config import AppConfig
    cfg = AppConfig.load()
    cfg.save()
    raw = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "super-secret-gemini" not in raw
    assert "tg-token-secret" not in raw
    assert "api-key-secret" not in raw
    assert "api-secret-secret" not in raw
