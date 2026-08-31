"""Telegram adapter — validates identity, routes to ControlPlane, uses NotifyQueue.

Does not call exchange APIs. Does not bypass Risk/Execution.
HTTP transport is injectable for tests (no network required).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from crypto.control.plane import CommandResult, ControlPlane, ControlResponse
from crypto.notify.queue import NotifyPriority, NotifyQueue
from crypto.telegram.menu import parse_command


@dataclass
class TelegramConfig:
    bot_token_ref: str = "telegram/bot_token"  # CredentialStore key — not the token
    authorized_chat_id: str = ""
    api_base: str = "https://api.telegram.org"


@dataclass
class TelegramAdapter:
    control: ControlPlane
    notify: NotifyQueue
    config: TelegramConfig
    # transport(method, payload) -> response dict; None = dry-run
    transport: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
    _last_retry_after: float = 0.0
    _mono: Callable[[], float] = time.monotonic
    _outbound_log: list[str] = field(default_factory=list)

    def handle_update(self, update: dict[str, Any]) -> ControlResponse | None:
        msg = update.get("message") or update.get("callback_query", {}).get("message")
        if not msg:
            return None
        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        text = ""
        if "message" in update:
            text = str(update["message"].get("text") or "")
        elif "callback_query" in update:
            text = str(update["callback_query"].get("data") or "")
        cmd = parse_command(text)
        if cmd is None:
            self.control.audit.record(chat_id, "unknown", "invalid", text[:40])
            return ControlResponse(CommandResult.INVALID, "unknown command")
        # Never accept PIN embedded as "PIN:123456" in free text for safety
        pin = None
        resp = self.control.dispatch(cmd, actor=f"tg:{chat_id}", chat_id=chat_id, pin=pin)
        # queue user-facing reply
        prio = NotifyPriority.P0 if cmd == "emergency_stop" else NotifyPriority.P2
        self.notify.publish(
            f"cmd_{cmd}",
            resp.message,
            priority=prio,
            dedupe_key=f"reply:{chat_id}:{cmd}",
        )
        return resp

    def flush_notifications(self, chat_id: str | None = None) -> int:
        """Send queued notifications via transport. Returns count sent."""
        target = chat_id or self.config.authorized_chat_id
        sent = 0
        now = self._mono()
        if now < self._last_retry_after:
            return 0
        while True:
            n = self.notify.pop_ready()
            if n is None:
                break
            payload = {"chat_id": target, "text": f"[{n.event}] {n.message}"}
            if self.transport is None:
                self._outbound_log.append(payload["text"])
                sent += 1
                continue
            try:
                resp = self.transport("sendMessage", payload)
                if resp.get("error_code") == 429:
                    retry = float(resp.get("parameters", {}).get("retry_after", 30))
                    self._last_retry_after = self._mono() + retry
                    # re-queue critical
                    self.notify.publish(
                        n.event, n.message, priority=n.priority, dedupe_key=n.dedupe_key
                    )
                    break
                sent += 1
            except Exception:  # noqa: BLE001
                # transport failure — trading continues; requeue P0/P1
                if n.priority <= NotifyPriority.P1:
                    self.notify.publish(
                        n.event, n.message, priority=n.priority, dedupe_key=n.dedupe_key
                    )
                break
        return sent
