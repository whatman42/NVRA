from god.security.totp import verify_totp

def test_totp_rfc6238_known_vector():
    # SHA-1 RFC 6238 secret = 12345678901234567890 (base32 below), t=59 => 94287082
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert verify_totp(secret, "287082", now=59)
