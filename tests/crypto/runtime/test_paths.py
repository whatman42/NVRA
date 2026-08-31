"""PathResolver and freeze-safe layout."""

from __future__ import annotations

from pathlib import Path

from crypto.runtime.paths import PathResolver, application_root, is_frozen


def test_not_frozen_in_dev() -> None:
    assert is_frozen() is False


def test_application_root_has_src_or_pyproject() -> None:
    root = application_root()
    assert (root / "pyproject.toml").is_file() or (root / "src" / "crypto").is_dir()


def test_resolver_creates_layout(tmp_path: Path) -> None:
    r = PathResolver(tmp_path)
    assert r.data_dir.is_dir()
    assert r.state_dir.is_dir()
    assert r.logs_dir.is_dir()
    assert r.sqlite_path().parent == r.state_dir
    d = r.as_dict()
    assert d["frozen"] == "False"
    assert "secret" not in str(d).lower()


def test_crypto_home_override(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CRYPTO_HOME", str(tmp_path / "portable"))
    from crypto.runtime.paths import env_override_root

    assert env_override_root() == (tmp_path / "portable").resolve()


def test_risk_policy_independent_of_paths(tmp_path: Path) -> None:
    from crypto.risk.policy import RiskPolicy

    PathResolver(tmp_path)
    a = RiskPolicy()
    b = RiskPolicy()
    assert a.max_position_pct == b.max_position_pct
