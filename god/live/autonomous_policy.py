"""Administrative autonomous trading policy — persisted, no secrets.

Stores only operator administrative intent that trading may run autonomously
after setup. Never stores passwords, API keys, tokens, or session credentials.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from god.persist.atomic import atomic_write_bytes

SCHEMA_VERSION = 1
POLICY_FILENAME = "autonomous_trading_policy.json"
FORBIDDEN_KEYS = frozenset(
    {
        "password",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "session_token",
        "private_key",
        "operator_ack",
        "unlock_token",
        "credential",
        "credentials",
    }
)


@dataclass
class AutonomousTradingPolicy:
    """Administrative authorization for autonomous trading after setup."""

    schema_version: int = SCHEMA_VERSION
    trading_mode: str = "PAPER"  # DEMO | PAPER | LIVE
    autonomous_live: bool = False
    autonomous_enabled: bool = True  # DEMO/PAPER autonomous loop after setup
    updated_at: float = field(default_factory=time.time)
    source: str = "administrative"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "trading_mode": self.trading_mode,
            "autonomous_live": bool(self.autonomous_live),
            "autonomous_enabled": bool(self.autonomous_enabled),
            "updated_at": self.updated_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutonomousTradingPolicy":
        if not isinstance(data, dict):
            raise ValueError("policy_not_object")
        for k in data:
            if str(k).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"forbidden_key:{k}")
        mode = str(data.get("trading_mode", "PAPER")).upper()
        if mode not in ("DEMO", "PAPER", "LIVE"):
            mode = "PAPER"
        return cls(
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            trading_mode=mode,
            autonomous_live=bool(data.get("autonomous_live", False)),
            autonomous_enabled=bool(data.get("autonomous_enabled", True)),
            updated_at=float(data.get("updated_at", time.time())),
            source=str(data.get("source", "administrative")),
        )


def default_policy_path(data_dir: Optional[Path] = None) -> Path:
    root = Path(data_dir) if data_dir else Path.home() / ".nvrafx"
    return root / POLICY_FILENAME


def load_policy(path: Path) -> Optional[AutonomousTradingPolicy]:
    """Load policy. Corrupt / forbidden content → None (fail-closed for LIVE)."""
    try:
        if not path.is_file():
            return None
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return AutonomousTradingPolicy.from_dict(data)
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return None


def save_policy(policy: AutonomousTradingPolicy, path: Path) -> None:
    """Atomic write, mode 0600, directory 0700. Strips any forbidden keys."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    payload = policy.to_dict()
    for k in list(payload.keys()):
        if k.lower() in FORBIDDEN_KEYS:
            raise ValueError(f"forbidden_key:{k}")
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(path, data)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def enable_autonomous_live(path: Path, *, mode: str = "LIVE") -> AutonomousTradingPolicy:
    """Administrative action: authorize autonomous LIVE (no secrets)."""
    mode = mode.upper() if mode.upper() in ("DEMO", "PAPER", "LIVE") else "LIVE"
    pol = AutonomousTradingPolicy(
        trading_mode=mode,
        autonomous_live=(mode == "LIVE"),
        autonomous_enabled=True,
        updated_at=time.time(),
        source="administrative",
    )
    save_policy(pol, path)
    return pol


def enable_autonomous_paper(path: Path) -> AutonomousTradingPolicy:
    pol = AutonomousTradingPolicy(
        trading_mode="PAPER",
        autonomous_live=False,
        autonomous_enabled=True,
        updated_at=time.time(),
        source="administrative",
    )
    save_policy(pol, path)
    return pol
