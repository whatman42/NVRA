from __future__ import annotations
from typing import Optional

SERVICE = "NVRA-UNIFIED"

class SecretStore:
    """Windows Credential Manager via keyring; memory-only fallback for CI/non-Windows tests."""
    def __init__(self) -> None:
        self._memory: dict[str, str] = {}
        try:
            import keyring
            self._keyring = keyring
        except Exception:
            self._keyring = None

    def set(self, key: str, value: str) -> None:
        if self._keyring is not None:
            self._keyring.set_password(SERVICE, key, value)
        else:
            self._memory[key] = value

    def get(self, key: str) -> Optional[str]:
        if self._keyring is not None:
            try:
                return self._keyring.get_password(SERVICE, key)
            except Exception:
                return None
        return self._memory.get(key)

    def delete(self, key: str) -> None:
        if self._keyring is not None:
            try:
                self._keyring.delete_password(SERVICE, key)
            except Exception:
                pass
        else:
            self._memory.pop(key, None)

    # --- Telegram ---
    def set_telegram(self, token: str, chat_id: str) -> None:
        self.set("telegram.token", token)
        self.set("telegram.chat_id", chat_id)

    def telegram(self) -> tuple[Optional[str], Optional[str]]:
        return self.get("telegram.token"), self.get("telegram.chat_id")

    def delete_telegram(self) -> None:
        self.delete("telegram.token")
        self.delete("telegram.chat_id")

    def telegram_configured(self) -> bool:
        tok, chat = self.telegram()
        return bool(tok and chat)

    # --- TOTP / MFA ---
    def set_totp_secret(self, secret_b32: str) -> None:
        self.set("security.totp.secret", secret_b32)

    def totp_secret(self) -> Optional[str]:
        return self.get("security.totp.secret")

    def delete_totp_secret(self) -> None:
        self.delete("security.totp.secret")

    def totp_configured(self) -> bool:
        return bool(self.totp_secret())

    # --- Cloud backup key ---
    def set_cloud_backup_key(self, key: str) -> None:
        self.set("cloud.backup.key", key)

    def cloud_backup_key(self) -> Optional[str]:
        return self.get("cloud.backup.key")

    # --- Google OAuth token (never put in config.json) ---
    def set_google_oauth_token(self, token_json: str) -> None:
        self.set("google.oauth.token", token_json)

    def google_oauth_token(self) -> Optional[str]:
        return self.get("google.oauth.token")

    def delete_google_oauth_token(self) -> None:
        self.delete("google.oauth.token")

    # --- Exchange / Crypto ---
    def set_exchange(self, broker: str, account_id: str, api_key: str, api_secret: str) -> None:
        self.set(f"exchange.{broker}.{account_id}.key", api_key)
        self.set(f"exchange.{broker}.{account_id}.secret", api_secret)

    def exchange(self, broker: str, account_id: str = "default") -> tuple[Optional[str], Optional[str]]:
        return (
            self.get(f"exchange.{broker}.{account_id}.key"),
            self.get(f"exchange.{broker}.{account_id}.secret"),
        )

    def delete_exchange(self, broker: str, account_id: str = "default") -> None:
        self.delete(f"exchange.{broker}.{account_id}.key")
        self.delete(f"exchange.{broker}.{account_id}.secret")

    def exchange_configured(self, broker: str, account_id: str = "default") -> bool:
        k, s = self.exchange(broker, account_id)
        return bool(k and s)

    # --- Gemini API key (secure store; env is fallback only) ---
    def set_gemini_api_key(self, key: str) -> None:
        self.set("gemini.api_key", key.strip())

    def gemini_api_key(self) -> Optional[str]:
        """Priority: keyring → GEMINI_API_KEY env (compatibility) → None."""
        stored = self.get("gemini.api_key")
        if stored:
            return stored
        import os
        env = os.environ.get("GEMINI_API_KEY", "").strip()
        return env or None

    def delete_gemini_api_key(self) -> None:
        self.delete("gemini.api_key")

    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key())
