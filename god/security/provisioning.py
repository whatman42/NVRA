"""TOTP provisioning helpers for Google Authenticator-compatible apps."""
from __future__ import annotations
import base64, secrets, urllib.parse

def generate_totp_secret(length: int = 20) -> str:
    return base64.b32encode(secrets.token_bytes(length)).decode("ascii").rstrip("=")

def otpauth_uri(secret: str, account: str, issuer: str = "NVRA") -> str:
    label = urllib.parse.quote(f"{issuer}:{account}")
    query = urllib.parse.urlencode({"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": 6, "period": 30})
    return f"otpauth://totp/{label}?{query}"
