"""Device registration and revocation."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .models import DeviceRecord, utc_now


class DeviceStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._devices: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._devices = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._devices = dict(data.get("devices") or {})
        except (OSError, json.JSONDecodeError):
            self._devices = {}

    def _save(self) -> None:
        payload = {"version": 1, "devices": self._devices}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def register(
        self,
        *,
        user_id: str,
        label: str = "",
        os_name: str = "",
        app_version: str = "0.0.0",
        device_id: Optional[str] = None,
    ) -> DeviceRecord:
        did = device_id or str(uuid.uuid4())
        rec = DeviceRecord(
            device_id=did,
            user_id=user_id,
            label=label,
            os_name=os_name,
            app_version=app_version,
            last_seen=utc_now(),
            status="ACTIVE",
        )
        self._devices[did] = rec.to_dict()
        self._save()
        return rec

    def heartbeat(self, device_id: str) -> Optional[DeviceRecord]:
        data = self._devices.get(device_id)
        if not data:
            return None
        rec = DeviceRecord.from_dict(data)
        if rec.status == "REVOKED":
            return rec
        rec.last_seen = utc_now()
        self._devices[device_id] = rec.to_dict()
        self._save()
        return rec

    def revoke(self, device_id: str) -> Optional[DeviceRecord]:
        data = self._devices.get(device_id)
        if not data:
            return None
        rec = DeviceRecord.from_dict(data)
        rec.status = "REVOKED"
        self._devices[device_id] = rec.to_dict()
        self._save()
        return rec

    def for_user(self, user_id: str) -> List[DeviceRecord]:
        return [
            DeviceRecord.from_dict(d)
            for d in self._devices.values()
            if d.get("user_id") == user_id
        ]

    def is_allowed(self, device_id: str, user_id: str) -> bool:
        data = self._devices.get(device_id)
        if not data:
            return False
        rec = DeviceRecord.from_dict(data)
        return rec.user_id == user_id and rec.status == "ACTIVE"
