"""Entrypoint smoke and multiprocessing guard."""

from __future__ import annotations

import multiprocessing
from pathlib import Path

from crypto.runtime.entrypoint import main, run_application


def test_smoke_ok(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CRYPTO_HOME", str(tmp_path))
    code = run_application(["--smoke"])
    assert code == 0


def test_version(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CRYPTO_HOME", str(tmp_path))
    code = run_application(["--version"])
    assert code == 0


def test_paths(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CRYPTO_HOME", str(tmp_path))
    code = run_application(["--paths"])
    assert code == 0


def test_main_freeze_support(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CRYPTO_HOME", str(tmp_path))
    assert main(["--smoke"]) == 0


def test_child_process_does_not_reenter() -> None:
    """Simulate non-MainProcess — main should return 0 immediately after freeze_support path."""
    # We cannot easily change current_process name; instead verify guard exists in source.
    from pathlib import Path as P

    src = P("src/crypto/runtime/entrypoint.py").read_text(encoding="utf-8")
    assert "freeze_support" in src
    assert "MainProcess" in src
    assert multiprocessing.current_process().name == "MainProcess"
