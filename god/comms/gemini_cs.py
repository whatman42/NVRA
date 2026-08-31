"""Gemini Customer Service — information only. NEVER trading authority.

If GEMINI_API_KEY is unset or API fails → local fallback.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional


# Explicitly refuse trading/admin intent
_BLOCKED_PATTERNS = (
    r"\b(buy|sell|order|execute|trade|sl\b|tp\b|lot size)\b",
    r"\b(change risk|bypass risk|disable risk)\b",
    r"\b(create admin|jadi admin|promote|revoke license|set expiry)\b",
    r"\b(password|private key|api key|broker (login|password)|kata sandi)\b",
)


@dataclass
class CSResponse:
    ok: bool
    source: str  # "gemini" | "local_fallback" | "refused"
    text: str


class GeminiCustomerService:
    """Optional Gemini; always safe local fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "").strip()
        self.enabled = bool(self.api_key)

    def _refused(self, user_text: str) -> Optional[str]:
        low = user_text.lower()
        for pat in _BLOCKED_PATTERNS:
            if re.search(pat, low):
                return (
                    "Saya hanya asisten informasi. Saya tidak dapat membuat order, "
                    "mengubah risk, license, admin, atau mengakses credential."
                )
        return None

    def _local_fallback(self, user_text: str) -> str:
        low = user_text.lower()
        if "trial" in low:
            return (
                "Mode Trial: paper/demo saja, tanpa login. Tidak ada akses admin, "
                "license, atau live trading."
            )
        if "license" in low or "lisensi" in low:
            return (
                "License dikelola administrator (ADMIN MODE). Status: ACTIVE / EXPIRED / "
                "REVOKED / SUSPENDED. Client tidak dapat mengubah expiry lokal."
            )
        if "mt5" in low or "metatrader" in low:
            return (
                "NUNG mendeteksi MT5 secara otomatis. Mode DEMO/LIVE diambil dari terminal, "
                "bukan pilihan manual sebagai sumber kebenaran."
            )
        if "login" in low or "register" in low:
            return (
                "Register selalu membuat role CLIENT. Root Admin hanya lewat inisialisasi "
                "kriptografi pertama kali — bukan username 'admin'."
            )
        if "chat" in low or "voice" in low:
            return (
                "Chat dan voice hanya komunikasi. Tidak dapat menempatkan order atau "
                "melewati Risk Engine."
            )
        return (
            "NUNG Customer Service (local fallback). Tanyakan tentang Trial, Login, "
            "License, MT5, Chat, atau Dashboard. Fitur trading tetap melewati Risk Engine."
        )

    def ask(self, user_text: str, *, display_name: str = "") -> CSResponse:
        if not user_text or not str(user_text).strip():
            return CSResponse(False, "refused", "Pesan kosong.")
        refused = self._refused(user_text)
        if refused:
            return CSResponse(True, "refused", refused)

        if not self.enabled:
            text = self._local_fallback(user_text)
            if display_name:
                text = f"{display_name}, {text[0].lower() + text[1:]}" if text else text
            return CSResponse(True, "local_fallback", text)

        # Optional Gemini HTTP — fail closed to local fallback (no key in logs)
        try:
            import json
            import urllib.request

            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-1.5-flash:generateContent?key={self.api_key}"
            )
            system = (
                "You are NUNG customer-service only. Never place trades, change risk, "
                "licenses, admin roles, or request/reveal secrets. Answer in the user language."
            )
            body = json.dumps(
                {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": f"{system}\n\nUser: {user_text}"}],
                        }
                    ]
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            parts = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])
            )
            text = parts[0].get("text") if parts else None
            if not text:
                raise RuntimeError("empty_gemini")
            # Second-pass refuse if model drifts
            if self._refused(text):
                return CSResponse(True, "refused", self._refused(user_text) or text)
            return CSResponse(True, "gemini", text.strip())
        except Exception:
            return CSResponse(True, "local_fallback", self._local_fallback(user_text))
