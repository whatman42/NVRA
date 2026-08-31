import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from god.broker.modes import BrokerMode, BrokerModePolicy, REAL_CONFIRMATION


def test_demo_is_valid_without_real_authorization(monkeypatch):
    monkeypatch.delenv("NVRA_REAL_TRADING_ENABLE", raising=False)
    monkeypatch.delenv("NVRA_REAL_TRADING_CONFIRM", raising=False)
    ok, reasons = BrokerModePolicy("binance", BrokerMode.DEMO).validate()
    assert ok and not reasons


def test_real_requires_explicit_two_factor_environment_gate(monkeypatch):
    monkeypatch.setenv("NVRA_REAL_TRADING_ENABLE", "true")
    monkeypatch.setenv("NVRA_REAL_TRADING_CONFIRM", REAL_CONFIRMATION)
    ok, _ = BrokerModePolicy("binance", BrokerMode.REAL, sandbox=False, allow_real=False).validate()
    assert not ok


def test_real_passes_only_when_policy_and_env_all_agree(monkeypatch):
    monkeypatch.setenv("NVRA_REAL_TRADING_ENABLE", "true")
    monkeypatch.setenv("NVRA_REAL_TRADING_CONFIRM", REAL_CONFIRMATION)
    ok, reasons = BrokerModePolicy("binance", BrokerMode.REAL, sandbox=False, allow_real=True).validate()
    assert ok and not reasons
