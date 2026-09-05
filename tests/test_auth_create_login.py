"""Auth Create Account / Login — clear reasons, no default password, no plaintext."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def auth_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    return tmp_path


def test_create_account_and_login_success(auth_home: Path):
    from nvra_unified.auth import create_account, login, enrollment_required

    assert enrollment_required() is True
    r = create_account("operator1", "strong-pass-99")
    assert r.ok is True
    assert enrollment_required() is False
    raw = (auth_home / "auth_verifier.json").read_text(encoding="utf-8")
    assert "strong-pass-99" not in raw
    data = json.loads(raw)
    assert "verifier" in data and "$" in data["verifier"]
    ok = login("operator1", "strong-pass-99")
    assert ok.ok is True


def test_wrong_password(auth_home: Path):
    from nvra_unified.auth import create_account, login, AuthReason

    assert create_account("operator1", "strong-pass-99").ok
    bad = login("operator1", "wrong-password")
    assert bad.ok is False
    assert bad.reason is AuthReason.WRONG_PASSWORD


def test_duplicate_account(auth_home: Path):
    from nvra_unified.auth import create_account, AuthReason

    assert create_account("operator1", "strong-pass-99").ok
    dup = create_account("other", "another-pass-99")
    assert dup.ok is False
    assert dup.reason is AuthReason.ALREADY_ENROLLED


def test_missing_enrollment_login(auth_home: Path):
    from nvra_unified.auth import login, AuthReason

    r = login("anyone", "whatever12")
    assert r.ok is False
    assert r.reason is AuthReason.ENROLLMENT_REQUIRED


def test_empty_credentials(auth_home: Path):
    from nvra_unified.auth import create_account, login, AuthReason

    assert create_account("", "").reason is AuthReason.EMPTY_CREDENTIALS
    assert login("", "x").reason is AuthReason.EMPTY_CREDENTIALS


def test_no_default_password(auth_home: Path):
    from nvra_unified.auth import login

    for user, pw in (("admin", "admin"), ("nvra", "nvra"), ("", "")):
        assert login(user, pw).ok is False
