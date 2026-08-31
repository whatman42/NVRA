"""Telegram adapter routing and failure isolation."""

from __future__ import annotations

from crypto.control import ControlPlane
from crypto.notify import NotifyQueue
from crypto.telegram import TelegramAdapter, TelegramConfig, parse_command


def test_parse_menu() -> None:
    assert parse_command("💰 SALDO") == "saldo"
    assert parse_command("/risk") == "risk_status"
    assert parse_command("nope") is None


def test_handle_update() -> None:
    cp = ControlPlane()
    cp.authorize_chat("42")
    ad = TelegramAdapter(cp, NotifyQueue(), TelegramConfig(authorized_chat_id="42"))
    resp = ad.handle_update({"message": {"chat": {"id": 42}, "text": "/saldo"}})
    assert resp is not None
    assert resp.result.name == "OK"


def test_telegram_failure_trading_continues() -> None:
    cp = ControlPlane()
    cp.authorize_chat("1")
    q = NotifyQueue()

    def boom(method: str, payload: dict) -> dict:
        raise RuntimeError("network down")

    ad = TelegramAdapter(cp, q, TelegramConfig(authorized_chat_id="1"), transport=boom)
    q.publish(
        "EMERGENCY",
        "stop",
        priority=__import__("crypto.notify", fromlist=["NotifyPriority"]).NotifyPriority.P0,
    )
    # flush fails but does not raise to trading
    ad.flush_notifications()
    assert cp.runtime.emergency_stop is False  # trading state untouched by notify fail


def test_retry_after() -> None:
    from crypto.notify import NotifyPriority

    cp = ControlPlane()
    q = NotifyQueue()
    calls = {"n": 0}

    def transport(method: str, payload: dict) -> dict:
        calls["n"] += 1
        return {"error_code": 429, "parameters": {"retry_after": 60}}

    ad = TelegramAdapter(cp, q, TelegramConfig(authorized_chat_id="1"), transport=transport)
    q.publish("x", "hi", priority=NotifyPriority.P1)
    sent = ad.flush_notifications()
    assert sent == 0
    assert q.pending_count() >= 1
