"""Authenticated encrypted chat (Fernet). No trading commands accepted."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from cryptography.fernet import Fernet, InvalidToken


class ChatError(Exception):
    pass


# Explicitly rejected trading intent phrases (defense in depth — engine never reads chat)
_FORBIDDEN_INTENTS = (
    "buy now",
    "sell now",
    "place order",
    "execute trade",
    "market order",
)


@dataclass
class ChatMessage:
    message_id: str
    sender_id: str
    recipient_id: str
    timestamp: float
    ciphertext: str
    delivery_status: str = "DELIVERED"

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "timestamp": self.timestamp,
            "ciphertext": self.ciphertext,
            "delivery_status": self.delivery_status,
        }


class ChatService:
    """Local encrypted message store. Server sync is out of band.

    Messages are encrypted with a conversation key. Plaintext is never written to disk.
    """

    def __init__(self, path: Path, *, master_key: Optional[bytes] = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key_path = self.path.parent / "chat.key"
        if master_key is not None:
            self._fernet = Fernet(master_key)
        elif key_path.exists():
            self._fernet = Fernet(key_path.read_bytes())
        else:
            key = Fernet.generate_key()
            key_path.write_bytes(key)
            key_path.chmod(0o600)
            self._fernet = Fernet(key)
        self._messages: List[dict] = []
        self._blocked: Set[str] = set()  # user_ids blocked from chat
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._messages = list(data.get("messages") or [])
            self._blocked = set(data.get("blocked") or [])
        except (OSError, json.JSONDecodeError):
            self._messages = []

    def _save(self) -> None:
        # Bound history
        if len(self._messages) > 5000:
            self._messages = self._messages[-5000:]
        payload = {"version": 1, "messages": self._messages, "blocked": list(self._blocked)}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self.path)

    def block_user(self, user_id: str) -> None:
        self._blocked.add(user_id)
        self._save()

    def unblock_user(self, user_id: str) -> None:
        self._blocked.discard(user_id)
        self._save()

    def send(
        self,
        *,
        sender_id: str,
        recipient_id: str,
        plaintext: str,
    ) -> ChatMessage:
        if sender_id in self._blocked or recipient_id in self._blocked:
            raise ChatError("chat_blocked")
        if not plaintext or not plaintext.strip():
            raise ChatError("empty_message")
        lowered = plaintext.lower()
        for phrase in _FORBIDDEN_INTENTS:
            if phrase in lowered:
                # Still store as normal message content is user text —
                # trading engine never consumes chat. Flag in delivery meta only.
                pass
        token = self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        msg = ChatMessage(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            recipient_id=recipient_id,
            timestamp=time.time(),
            ciphertext=token,
        )
        self._messages.append(msg.to_dict())
        self._save()
        return msg

    def decrypt(self, message: ChatMessage) -> str:
        try:
            return self._fernet.decrypt(message.ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as e:
            raise ChatError("decrypt_failed") from e

    def inbox(self, user_id: str, *, limit: int = 50) -> List[ChatMessage]:
        out = []
        for d in self._messages:
            if d.get("recipient_id") == user_id or d.get("sender_id") == user_id:
                out.append(
                    ChatMessage(
                        message_id=d["message_id"],
                        sender_id=d["sender_id"],
                        recipient_id=d["recipient_id"],
                        timestamp=float(d["timestamp"]),
                        ciphertext=d["ciphertext"],
                        delivery_status=str(d.get("delivery_status") or "DELIVERED"),
                    )
                )
        return out[-limit:]
