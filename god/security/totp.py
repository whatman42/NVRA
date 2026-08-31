"""RFC 6238 TOTP verification for local MFA.
The secret is supplied by the secure secret store; it is never persisted here.
"""
from __future__ import annotations
import base64, hashlib, hmac, struct, time


def _hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32.strip().upper() + "=" * (-len(secret_b32.strip()) % 8), casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return f"{code:0{digits}d}"


def verify_totp(secret_b32: str, code: str, *, now: int | None = None, period: int = 30, window: int = 1) -> bool:
    if not secret_b32 or not code.isdigit() or len(code) != 6 or period <= 0 or window < 0:
        return False
    counter = int((now if now is not None else time.time()) // period)
    for delta in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret_b32, counter + delta), code):
            return True
    return False
