"""Admin client dashboard view models — no secrets exposed."""
from __future__ import annotations

import time
from typing import Any, Optional

from .roles import Role
from .store import ControlPlaneStore

# Online if heartbeat age < 5 minutes
ONLINE_THRESHOLD_SEC = 300.0
# Soft offline/grace band
GRACE_THRESHOLD_SEC = 900.0

ALLOWED_ADMIN_ACTIONS = frozenset({
    "view",
    "disable_client",
    "enable_client",
    "revoke_license",
    "disable_license",
    "generate_license",
    "extend_license",
    "disable_device",
    "revoke_device",
    "revoke_session",
    "publish_model",
    "update_approved_policy",
})

FORBIDDEN_ADMIN_ACTIONS = frozenset({
    "bypass_risk_governor",
    "force_live_order",
    "change_immutable_risk_ceiling",
    "access_client_secrets",
    "access_private_keys",
    "download_master_dataset",
    "download_private_model_weights",
})

_SECRET_KEY_FRAGMENTS = (
    "password", "secret", "token", "api_key", "apikey", "api_secret",
    "private_key", "credential", "session_secret", "telegram",
)


def _strip_secrets(data: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not data:
        return {}
    out: dict[str, Any] = {}
    for k, v in data.items():
        kl = str(k).lower().replace("-", "_")
        if any(frag in kl for frag in _SECRET_KEY_FRAGMENTS):
            continue
        if isinstance(v, dict):
            out[str(k)] = _strip_secrets(v)
        else:
            out[str(k)] = v
    return out


def derive_connection_status(
    *,
    license_status: str,
    account_status: str,
    last_hb_age: Optional[float],
    safe_mode: bool,
) -> str:
    """Derive status from real state — not a UI placeholder."""
    if license_status in {"REVOKED", "EXPIRED", "DISABLED"}:
        return "LICENSE_BLOCKED"
    if account_status in {"REVOKED", "DISABLED"}:
        return "LICENSE_BLOCKED"
    if safe_mode:
        return "SAFE_MODE"
    if last_hb_age is None:
        return "OFFLINE"
    if last_hb_age < ONLINE_THRESHOLD_SEC:
        return "ONLINE"
    if last_hb_age < GRACE_THRESHOLD_SEC:
        return "OFFLINE_GRACE"
    return "OFFLINE"


def derive_heartbeat_class(
    *,
    license_status: str,
    device_status: str,
    last_hb_age: Optional[float],
    safe_mode: bool,
) -> str:
    """Distinguish offline vs revoke — timeout alone is never LICENSE_REVOKED."""
    if license_status == "REVOKED":
        return "LICENSE_REVOKED"
    if device_status == "REVOKED":
        return "DEVICE_REVOKED"
    if safe_mode:
        return "SAFE_MODE"
    if last_hb_age is None or last_hb_age >= ONLINE_THRESHOLD_SEC:
        return "CLIENT_OFFLINE"
    return "OK"


def client_overview_row(store: ControlPlaneStore, account_id: str) -> dict[str, Any]:
    acc = store.accounts[account_id]
    licenses = [L for L in store.licenses.values() if L.account_id == account_id]
    devices = [d for d in store.devices.values() if d.account_id == account_id]
    hbs = [h for h in store.heartbeats if h.account_id == account_id]
    last_hb = max((h.timestamp for h in hbs), default=0.0)
    age = time.time() - last_hb if last_hb else None
    lic = licenses[-1] if licenses else None
    safe = any(h.safe_mode for h in hbs[-3:]) if hbs else False
    dev_status = devices[-1].status.value if devices else "NONE"
    lic_status = lic.status.value if lic else "NONE"
    status = derive_connection_status(
        license_status=lic_status,
        account_status=acc.status.value,
        last_hb_age=age,
        safe_mode=safe,
    )
    hb_class = derive_heartbeat_class(
        license_status=lic_status,
        device_status=dev_status,
        last_hb_age=age,
        safe_mode=safe,
    )
    latest_hb = hbs[-1] if hbs else None
    return {
        "client_id": acc.id,
        "username": acc.username,
        "account_status": acc.status.value,
        "license_status": lic_status,
        "license_expiry": lic.expires_at if lic else None,
        "license_unlimited": bool(lic and lic.expires_at is None) if lic else False,
        "device_count": len(devices),
        "online": status == "ONLINE",
        "last_heartbeat_age_sec": age,
        "client_version": devices[-1].client_version if devices else "",
        "os_name": devices[-1].os_name if devices else "",
        "status": status,
        "heartbeat_class": hb_class,
        "runtime_status": (latest_hb.runtime_status if latest_hb else "UNKNOWN"),
        "safe_mode": safe,
        "execution_mode": "PAPER",
    }


def admin_list_clients(store: ControlPlaneStore) -> list[dict[str, Any]]:
    return [client_overview_row(store, a.id) for a in store.list_clients()]


def admin_dashboard_summary(store: ControlPlaneStore) -> dict[str, Any]:
    rows = admin_list_clients(store)
    return {
        "clients_total": len(rows),
        "online": sum(1 for r in rows if r["status"] == "ONLINE"),
        "offline": sum(1 for r in rows if r["status"] in {"OFFLINE", "OFFLINE_GRACE"}),
        "safe_mode": sum(1 for r in rows if r["status"] == "SAFE_MODE"),
        "license_blocked": sum(1 for r in rows if r["status"] == "LICENSE_BLOCKED"),
        "clients": rows,
    }


def client_detail(
    store: ControlPlaneStore,
    account_id: str,
    *,
    telemetry: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Full client detail for Admin. Secrets stripped from telemetry."""
    row = client_overview_row(store, account_id)
    safe_tel = _strip_secrets(telemetry)

    portfolio = {
        "mode": "PAPER",
        "balance": safe_tel.get("balance"),
        "equity": safe_tel.get("equity"),
        "available_balance": safe_tel.get("available_balance"),
        "open_positions": safe_tel.get("open_positions"),
        "exposure": safe_tel.get("exposure"),
        "pnl": safe_tel.get("pnl") or safe_tel.get("realized_pnl"),
        "drawdown": safe_tel.get("drawdown"),
        "risk_state": safe_tel.get("risk_state") or safe_tel.get("risk_governor") or "NORMAL",
        "note": "portfolio_from_telemetry_only",
    }

    risk = {
        "governor": safe_tel.get("risk_governor") or safe_tel.get("risk_state") or "NORMAL",
        "exposure": safe_tel.get("exposure"),
        "limit_status": safe_tel.get("risk_limit_status") or "OK",
        "block_reason": safe_tel.get("risk_block_reason") or "",
        "safe_mode": row["safe_mode"],
        "admin_can_bypass": False,
        "immutable_ceiling": True,
    }

    model = {
        "active_model": safe_tel.get("active_model"),
        "version": safe_tel.get("model_version"),
        "registry_id": safe_tel.get("model_registry_id"),
        "published_at": safe_tel.get("model_published_at"),
        "health": safe_tel.get("model_health") or "UNKNOWN",
        "drift_ood": safe_tel.get("drift_ood") or "UNKNOWN",
        "inference_status": safe_tel.get("inference_status") or "UNKNOWN",
        "scope": "CLIENT_PUBLISHED",
        "admin_private_visible": False,
    }

    system = {
        "cpu": safe_tel.get("cpu"),
        "ram": safe_tel.get("ram"),
        "disk": safe_tel.get("disk"),
        "gpu": safe_tel.get("gpu"),
        "app_version": safe_tel.get("app_version") or row.get("client_version"),
        "os": safe_tel.get("os") or row.get("os_name"),
        "uptime_sec": safe_tel.get("uptime_sec"),
        "control_plane_connection": "ONLINE" if row["online"] else "OFFLINE",
        "safe_mode": row["safe_mode"],
    }

    sessions = [
        {
            "id": s.id,
            "device_id": s.device_id,
            "expires_at": s.expires_at,
            "revoked": s.revoked,
        }
        for s in store.sessions.values()
        if s.account_id == account_id
    ]

    return {
        **row,
        "devices": [d.to_dict() for d in store.devices.values() if d.account_id == account_id],
        "licenses": [
            {
                "id": L.id,
                "username": L.username,
                "status": L.status.value,
                "issued_at": L.issued_at,
                "expires_at": L.expires_at,
                "unlimited": L.expires_at is None,
                "has_signature": bool(L.signature),
            }
            for L in store.licenses.values()
            if L.account_id == account_id
        ],
        "sessions": sessions,
        "portfolio_summary": portfolio,
        "risk_status": risk,
        "model_status": model,
        "system_health": system,
        "runtime": {
            "mode": "PAPER",
            "status": row.get("runtime_status") or "UNKNOWN",
            "safe_mode": row["safe_mode"],
        },
        "forbidden_capabilities": sorted(FORBIDDEN_ADMIN_ACTIONS),
        "admin_capabilities": {
            "bypass_risk_governor": False,
            "force_live_order": False,
            "change_immutable_risk_ceiling": False,
            "access_client_secrets": False,
            "view": True,
            "revoke_license": True,
            "disable_device": True,
        },
    }
