"""Portable / installed PathResolver and CWD independence."""

from __future__ import annotations

from pathlib import Path

from crypto.runtime.paths import (
    DeployMode,
    PathResolver,
    detect_deploy_mode,
    user_data_root,
    write_portable_marker,
)


def test_portable_marker(tmp_path: Path) -> None:
    write_portable_marker(tmp_path)
    assert detect_deploy_mode(tmp_path) is DeployMode.PORTABLE
    r = PathResolver(tmp_path, mode=DeployMode.PORTABLE)
    assert r.root == tmp_path.resolve()
    assert r.state_dir.is_dir()
    assert r.models_dir.parent == r.root


def test_installed_uses_localappdata(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake_local = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))
    monkeypatch.delenv("CRYPTO_HOME", raising=False)
    prog = tmp_path / "ProgramFiles" / "CRYPTO"
    prog.mkdir(parents=True)
    # no .portable marker
    data = user_data_root(prog, DeployMode.INSTALLED)
    assert data == (fake_local / "CRYPTO").resolve()
    r = PathResolver(prog, mode=DeployMode.INSTALLED, data_root=data)
    assert r.sqlite_path().is_relative_to(fake_local.resolve())
    assert not str(r.sqlite_path()).startswith(str(prog))


def test_cwd_independence(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    write_portable_marker(tmp_path)
    monkeypatch.setenv("CRYPTO_HOME", str(tmp_path))
    # Change CWD to unrelated directory
    other = tmp_path / "othercwd"
    other.mkdir()
    monkeypatch.chdir(other)
    r = PathResolver(tmp_path, mode=DeployMode.PORTABLE)
    assert r.state_dir.is_dir()
    assert r.state_dir == tmp_path / "state"
    # Must not create state under CWD
    assert not (other / "state").exists()


def test_portable_copy_simulation(tmp_path: Path) -> None:
    """PC-A data folder copied to PC-B path."""
    pc_a = tmp_path / "pc_a"
    write_portable_marker(pc_a)
    ra = PathResolver(pc_a, mode=DeployMode.PORTABLE)
    (ra.state_dir / "marker.txt").write_text("state-from-a", encoding="utf-8")
    (ra.models_dir / "model.bin").write_bytes(b"\x00\x01")
    # Copy tree
    pc_b = tmp_path / "pc_b"
    import shutil

    shutil.copytree(pc_a, pc_b)
    rb = PathResolver(pc_b, mode=DeployMode.PORTABLE)
    assert (rb.state_dir / "marker.txt").read_text(encoding="utf-8") == "state-from-a"
    assert (rb.models_dir / "model.bin").read_bytes() == b"\x00\x01"
    assert rb.root == pc_b.resolve()
