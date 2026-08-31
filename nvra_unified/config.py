from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict

try:
    import yaml
except ImportError:  # optional until installed by runtime requirements
    yaml = None

from .auth import user_data_dir

@dataclass
class BrokerAccount:
    broker: str
    account_id: str = "default"
    enabled: bool = True
    mode: str = "PAPER"

@dataclass
class AppConfig:
    idx_initial_balance: float = 10_000_000.0
    idx_balance_reset: float = 10_000_000.0
    crypto_accounts: list[BrokerAccount] = field(default_factory=list)
    telegram_enabled: bool = False
    telegram_chat_id: str = ""
    forex_auto_detect_mt5: bool = True
    grace_stop_seconds: int = 10
    hardware_profile: str = "AUTO"
    data_version: int = 1
    google_account_email: str = ""
    google_drive_enabled: bool = False
    google_oauth_client_file: str = ""
    totp_enabled: bool = False
    license_service_url: str = ""
    device_binding_enabled: bool = True

    @classmethod
    def load(cls) -> "AppConfig":
        """Load persisted JSON, falling back to packaged YAML defaults.

        YAML is configuration-only; secrets are intentionally excluded. Existing
        JSON installations remain backward compatible.
        """
        json_path = user_data_dir() / "config.json"
        try:
            d = json.loads(json_path.read_text(encoding="utf-8"))
            d["crypto_accounts"] = [BrokerAccount(**x) for x in d.get("crypto_accounts", [])]
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        except Exception:
            pass
        yaml_path = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"
        try:
            if yaml is None or not yaml_path.exists():
                return cls()
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            portfolio = raw.get("portfolio", {})
            telegram = raw.get("telegram", {})
            cloud = raw.get("cloud", {})
            security = raw.get("security", {})
            return cls(
                idx_initial_balance=float(portfolio.get("initial_capital_idr", 10_000_000)),
                idx_balance_reset=float(portfolio.get("reset_capital_idr", 10_000_000)),
                telegram_enabled=bool(telegram.get("enabled", False)),
                google_account_email=str(cloud.get("google_account_email", "")),
                google_drive_enabled=bool(cloud.get("google_drive_enabled", False)),
                google_oauth_client_file=str(cloud.get("oauth_client_file", "")),
                totp_enabled=bool(security.get("totp_enabled", False)),
                license_service_url=str(security.get("license_service_url", "")),
                device_binding_enabled=bool(security.get("device_binding_enabled", True)),
            )
        except Exception:
            return cls()

    def save(self) -> Path:
        p = user_data_dir() / "config.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(p)
        return p
