"""Admin client dashboard view models — no secrets."""
from __future__ import annotations
import time
from typing import Any
from .store import ControlPlaneStore

def client_overview_row(store: ControlPlaneStore, account_id: str) -> dict[str, Any]:
    acc = store.accounts[account_id]
    licenses = [L for L in store.licenses.values() if L.account_id == account_id]
    devices = [d for d in store.devices.values() if d.account_id == account_id]
    hbs = [h for h in store.heartbeats if h.account_id == account_id]
    last_hb = max((h.timestamp for h in hbs), default=0.0)
    age = time.time() - last_hb if last_hb else None
    lic = licenses[-1] if licenses else None
    online = age is not None and age < 300
    safe = any(h.safe_mode for h in hbs[-3:]) if hbs else False
    status = "ONLINE" if online else "OFFLINE"
    if lic and lic.status.value in {"REVOKED", "EXPIRED", "DISABLED"}:
        status = "LICENSE_BLOCKED"
    if safe:
        status = "SAFE_MODE"
    return {
        "client_id": acc.id, "username": acc.username, "account_status": acc.status.value,
        "license_status": lic.status.value if lic else "NONE",
        "license_expiry": lic.expires_at if lic else None, "device_count": len(devices),
        "online": online, "last_heartbeat_age_sec": age,
        "client_version": devices[-1].client_version if devices else "",
        "os_name": devices[-1].os_name if devices else "", "status": status,
    }

def admin_list_clients(store: ControlPlaneStore) -> list[dict[str, Any]]:
    return [client_overview_row(store, a.id) for a in store.list_clients()]

def client_detail(store: ControlPlaneStore, account_id: str) -> dict[str, Any]:
    row = client_overview_row(store, account_id)
    return {
        **row,
        "devices": [d.to_dict() for d in store.devices.values() if d.account_id == account_id],
        "licenses": [L.to_dict() for L in store.licenses.values() if L.account_id == account_id],
        "portfolio_summary": {"note": "telemetry_placeholder", "mode": "PAPER"},
        "risk_status": "NORMAL",
        "model_status": {"active": None, "scope": "CLIENT_PUBLISHED"},
    }
