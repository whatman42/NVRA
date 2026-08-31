from god.security.provisioning import generate_totp_secret, otpauth_uri

def test_totp_provisioning_uri():
    s=generate_totp_secret(); u=otpauth_uri(s,"user@example.com")
    assert len(s) >= 32 and u.startswith("otpauth://totp/") and "issuer=NVRA" in u
