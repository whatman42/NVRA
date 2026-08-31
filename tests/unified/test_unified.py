from pathlib import Path
import os


def test_first_run_enrollment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    from nvra_unified.auth import enroll_first_user, verify_default_login, enrollment_required

    assert enrollment_required()
    assert enroll_first_user("operator", "strong-test-password")
    assert not enrollment_required()
    assert verify_default_login("operator", "strong-test-password")
    assert not verify_default_login("nung", "3201291609910002")
    assert not enroll_first_user("other", "another-password")


def test_enrolled_login_rejects_wrong_password(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    from nvra_unified.auth import enroll_first_user, verify_login

    assert enroll_first_user("operator", "strong-test-password")
    assert not verify_login("operator", "wrong-password")
    assert not verify_login("other", "strong-test-password")


def test_enrollment_file_is_private(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    from nvra_unified.auth import enroll_first_user

    assert enroll_first_user("operator", "strong-test-password")
    auth_file = tmp_path / "auth_verifier.json"
    if os.name == "posix":
        assert auth_file.stat().st_mode & 0o777 == 0o600
        assert auth_file.parent.stat().st_mode & 0o777 == 0o700


def test_no_legacy_default_credential(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NVRA_HOME", str(tmp_path))
    from nvra_unified.auth import verify_default_login, enrollment_required

    assert enrollment_required()
    assert not verify_default_login("nung", "3201291609910002")
