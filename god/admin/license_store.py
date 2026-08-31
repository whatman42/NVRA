"""License lifecycle: create, expiry, revoke, restore — bound to user_id."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from god.keygen.signing import SigningKeyPair

from .models import LicenseRecord, LicenseStatus, utc_now


class LicenseStore:
    def __init__(self, path: Path, keypair: SigningKeyPair):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.keypair = keypair
        self._licenses: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._licenses = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._licenses = dict(data.get("licenses") or {})
        except (OSError, json.JSONDecodeError):
            self._licenses = {}

    def _save(self) -> None:
        payload = {"version": 1, "licenses": self._licenses}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def create(
        self,
        *,
        user_id: str,
        username: str,
        expires_in_days: Optional[int] = None,
    ) -> LicenseRecord:
        issued = utc_now()
        expires_at = None
        if expires_in_days is not None:
            exp = datetime.now(timezone.utc) + timedelta(days=int(expires_in_days))
            expires_at = exp.isoformat()
        license_id = str(uuid.uuid4())
        material = f"{license_id}|{user_id}|{issued}|{expires_at or 'NONE'}".encode()
        signature = self.keypair.sign(material)
        rec = LicenseRecord(
            license_id=license_id,
            user_id=user_id,
            username=username,
            issued_at=issued,
            expires_at=expires_at,
            status=LicenseStatus.ACTIVE,
            signature=signature,
        )
        self._licenses[license_id] = rec.to_dict()
        self._save()
        return rec

    def get(self, license_id: str) -> Optional[LicenseRecord]:
        data = self._licenses.get(license_id)
        return LicenseRecord.from_dict(data) if data else None

    def for_user(self, user_id: str) -> List[LicenseRecord]:
        out = []
        for data in self._licenses.values():
            if data.get("user_id") == user_id:
                out.append(LicenseRecord.from_dict(data))
        return out

    def refresh_expiry_status(self, license_id: str) -> Optional[LicenseRecord]:
        rec = self.get(license_id)
        if rec is None:
            return None
        if rec.status == LicenseStatus.ACTIVE and rec.expires_at:
            if not rec.is_trading_allowed():
                rec.status = LicenseStatus.EXPIRED
                self._licenses[license_id] = rec.to_dict()
                self._save()
        return rec

    def revoke(self, license_id: str) -> Optional[LicenseRecord]:
        rec = self.get(license_id)
        if rec is None:
            return None
        rec.status = LicenseStatus.REVOKED
        self._licenses[license_id] = rec.to_dict()
        self._save()
        return rec

    def restore(self, license_id: str) -> Optional[LicenseRecord]:
        rec = self.get(license_id)
        if rec is None:
            return None
        # Restore only if not past expiry
        if rec.expires_at and not LicenseRecord(
            license_id=rec.license_id,
            user_id=rec.user_id,
            username=rec.username,
            issued_at=rec.issued_at,
            expires_at=rec.expires_at,
            status=LicenseStatus.ACTIVE,
            signature=rec.signature,
        ).is_trading_allowed():
            rec.status = LicenseStatus.EXPIRED
        else:
            rec.status = LicenseStatus.ACTIVE
        self._licenses[license_id] = rec.to_dict()
        self._save()
        return rec

    def trading_allowed_for_user(self, user_id: str) -> bool:
        for rec in self.for_user(user_id):
            self.refresh_expiry_status(rec.license_id)
            updated = self.get(rec.license_id)
            if updated and updated.is_trading_allowed():
                return True
        return False
