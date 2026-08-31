from __future__ import annotations
import threading, time, platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AppConfig
from .secrets import SecretStore
from .auth import user_data_dir
from god.licensing import check_device

@dataclass
class RuntimeStatus:
    running: bool = False
    stopping: bool = False
    stop_deadline: float = 0.0
    crypto: str = "STOPPED"
    forex: str = "STOPPED"
    idx: str = "STOPPED"
    telegram: str = "STOPPED"
    hardware: str = "UNKNOWN"
    ml_engine: str = "ADAPTIVE"
    risk: str = "ACTIVE"
    last_error: str = ""
    cycles: int = 0
    portfolios: dict[str, dict[str, float]] = field(default_factory=dict)

class UnifiedRuntime:
    """One supervisor for crypto + forex + IDX signal + Telegram services.
    It never bypasses broker risk/readiness gates. GUI closure does not stop it."""
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.load()
        self.secrets = SecretStore()
        self.status = RuntimeStatus()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._started = False
        self._detect_hardware()

    def _detect_hardware(self) -> None:
        try:
            import psutil
            gb = psutil.virtual_memory().total / 1024**3
            cpu = psutil.cpu_count(logical=True) or 1
            if gb <= 2.5: profile = "ULTRA_LITE"
            elif gb <= 4.5 or cpu <= 2: profile = "LITE"
            elif gb <= 8: profile = "BALANCED"
            elif gb <= 16: profile = "PERFORMANCE"
            else: profile = "EXTREME"
            self.status.hardware = f"{profile} ({gb:.1f}GB/{cpu}CPU)"
            self.config.hardware_profile = profile
        except Exception:
            self.status.hardware = "ULTRA_LITE"

    def start(self) -> None:
        with self._lock:
            if self._started and self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self.status.running = True
            self.status.stopping = False
            self.status.crypto = "READY"
            self.status.idx = "SIGNAL_ONLY"
            self.status.forex = "AUTO_DETECT"
            self.status.telegram = "READY" if self.secrets.telegram()[0] else "NOT_CONFIGURED"
            self._started = True
            self._thread = threading.Thread(target=self._loop, name="NVRA-Unified-Supervisor", daemon=False)
            self._thread.start()

    def request_grace_stop(self, seconds: int | None = None) -> None:
        with self._lock:
            if not self.status.running or self.status.stopping:
                return
            delay = max(2, int(seconds or self.config.grace_stop_seconds))
            self.status.stopping = True
            self.status.stop_deadline = time.time() + delay
            self.status.crypto = "DRAINING"
            self.status.forex = "DRAINING"
            self.status.idx = "DRAINING"
            self.status.telegram = "DRAINING"

    def force_stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self.status.running = False
        self.status.stopping = False
        for k in ("crypto","forex","idx","telegram"):
            setattr(self.status, k, "STOPPED")

    def _loop(self) -> None:
        while not self._stop.wait(1.0):
            with self._lock:
                self.status.cycles += 1
                if self.status.stopping and time.time() >= self.status.stop_deadline:
                    self._stop.set()
                    break
                if not self.status.stopping:
                    self._refresh_services()
        with self._lock:
            self.status.running = False
            self.status.stopping = False
            for k in ("crypto","forex","idx","telegram"):
                setattr(self.status, k, "STOPPED")

    def _refresh_services(self) -> None:
        # Keep lightweight; real market/execution work remains in the existing engines.
        try:
            from god.mt5_runtime.detect import detect_mt5
            result = detect_mt5()
            self.status.forex = "MT5_FOUND" if result.found else "MT5_SEARCHING"
        except Exception:
            self.status.forex = "MT5_UNAVAILABLE"
        if self.secrets.telegram()[0]:
            self.status.telegram = "READY"
        self.status.ml_engine = f"ADAPTIVE/{self.status.hardware.split(' ')[0]}"

    def reset_idx_balance(self) -> float:
        self.config.idx_initial_balance = self.config.idx_balance_reset
        self.config.save()
        return self.config.idx_initial_balance

    def portfolio_snapshot(self) -> dict[str, Any]:
        return {
            "IDX_SIM": {"cash": self.config.idx_initial_balance, "currency": "IDR"},
            "crypto": {f"{a.broker}:{a.account_id}": {"mode": a.mode} for a in self.config.crypto_accounts},
            "forex": {"source": "MT5 terminal", "mode": "BROKER_ACCOUNT"},
        }

    def cashout_request(self, broker: str, amount_idr: float) -> dict[str, Any]:
        """Create an auditable withdrawal request. Actual withdrawal is never guessed or silently executed.
        An exchange adapter must explicitly expose a verified withdrawal capability before execution."""
        if amount_idr <= 0:
            return {"ok": False, "reason": "invalid_amount"}
        return {
            "ok": False,
            "status": "REQUIRES_VERIFIED_WITHDRAWAL_CAPABILITY",
            "broker": broker,
            "amount_idr": float(amount_idr),
            "reason": "Existing CRYPTO adapters intentionally disable withdrawal; request recorded by caller.",
        }

    def device_status(self) -> dict[str, Any]:
        if not self.config.device_binding_enabled:
            return {"allowed": True, "status": "DISABLED"}
        result = check_device(
            self.config.google_account_email or "unconfigured",
            user_data_dir() / "device_identity.json",
            self.config.license_service_url,
        )
        return {"allowed": result.allowed, "status": result.status, "device_id": result.device_id, "account_id": result.account_id}

    def backup_to_google_drive(self, destination_dir: str | Path | None = None) -> dict[str, Any]:
        """Create an encrypted migration bundle and upload it when Google Drive is configured."""
        if not self.config.google_drive_enabled or not self.config.google_oauth_client_file:
            return {"ok": False, "status": "GOOGLE_DRIVE_NOT_CONFIGURED"}
        from god.cloud.google_drive import CloudBackupService, GoogleDriveBackup, SecureBackup
        key = self.secrets.cloud_backup_key()
        if not key:
            key = SecureBackup.generate_key().decode("ascii")
            self.secrets.set_cloud_backup_key(key)
        drive = GoogleDriveBackup(
            self.config.google_oauth_client_file,
            token_store_get=self.secrets.google_oauth_token,
            token_store_set=self.secrets.set_google_oauth_token,
        )
        service = CloudBackupService(drive, SecureBackup(key.encode("ascii")))
        return {"ok": True, "status": "UPLOADED", "result": service.export_and_upload(destination_dir or (user_data_dir() / "backup"), data_root=user_data_dir(), source_version="V7.1") }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.status.running,
                "stopping": self.status.stopping,
                "stop_deadline": self.status.stop_deadline,
                "crypto": self.status.crypto,
                "forex": self.status.forex,
                "idx": self.status.idx,
                "telegram": self.status.telegram,
                "hardware": self.status.hardware,
                "ml_engine": self.status.ml_engine,
                "risk": self.status.risk,
                "cycles": self.status.cycles,
                "portfolios": self.portfolio_snapshot(),
                "device": self.device_status(),
                "home": str(user_data_dir()),
                "platform": platform.platform(),
            }
