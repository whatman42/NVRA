"""Secret scan and kill-switch behaviour."""

from __future__ import annotations

from crypto.production.kill import KillAction, KillSwitch
from crypto.production.security import scan_text_for_secrets
from crypto.risk.policy import RiskPolicy


def test_secret_patterns_detected() -> None:
    hits = scan_text_for_secrets("api_secret = 'abcdefghijklmnopqrstuvwxyz0123'")
    assert hits


def test_clean_text() -> None:
    assert scan_text_for_secrets("mode=PAPER profile=LITE") == []


def test_pin_warning_not_flagged() -> None:
    # Documentation / safety comments must not trip secret scanner
    assert scan_text_for_secrets('Never accept PIN embedded as "PIN:123456"') == []


def test_kill_safe_mode_on_drawdown() -> None:
    k = KillSwitch(drawdown_pct=10.0, max_drawdown_pct=3.0)
    assert k.evaluate() is KillAction.SAFE_MODE


def test_kill_does_not_change_risk_policy() -> None:
    before = RiskPolicy()
    k = KillSwitch(daily_loss=100.0, max_daily_loss=1.0)
    k.evaluate()
    after = RiskPolicy()
    assert before.max_position_pct == after.max_position_pct
