"""User identity — cryptographic binding id, not filename security."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class IdentityError(Exception):
    """Invalid or mismatched identity."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class UserIdentity:
    """Stable user identity used for model binding and session auth."""

    user_id: str
    username: str
    display_name: str
    created_at: str
    public_binding: str  # hex digest binding material (not a secret)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "public_binding": self.public_binding,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserIdentity":
        try:
            return cls(
                user_id=str(data["user_id"]),
                username=str(data["username"]),
                display_name=str(data.get("display_name") or data["username"]),
                created_at=str(data["created_at"]),
                public_binding=str(data["public_binding"]),
            )
        except (KeyError, TypeError) as e:
            raise IdentityError(f"invalid identity payload: {e}") from e

    @staticmethod
    def create(username: str, display_name: Optional[str] = None) -> "UserIdentity":
        if not username or not username.strip():
            raise IdentityError("username required")
        uid = str(uuid.uuid4())
        created = _utc_now()
        binding_src = f"{uid}|{username.strip().lower()}|{created}"
        public_binding = hashlib.sha256(binding_src.encode("utf-8")).hexdigest()
        return UserIdentity(
            user_id=uid,
            username=username.strip(),
            display_name=(display_name or username).strip(),
            created_at=created,
            public_binding=public_binding,
        )
