"""Regression checks for phase-1 import/compatibility repairs."""


def test_legacy_runtime_entrypoint_imports():
    import importlib

    main = importlib.import_module("god.runtime.main")

    assert main.PRODUCT_VERSION
    assert main.main(["--version"]) == 0


def test_release_readiness_imports_and_headless_cycle():
    from god.release import FinalReleaseGate

    result = FinalReleaseGate().headless_cycle()
    assert result["started_state"] == "RUNNING"
    assert result["stopped_state"] == "STOPPED"
    assert result["live_trading_enabled"] is False
