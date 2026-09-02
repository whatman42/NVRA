"""Admin management actions — audited, no risk/live/secret authority."""
from __future__ import annotations

from typing import Any, Optional

from .dashboard import ALLOWED_ADMIN_ACTIONS, FORBIDDEN_ADMIN_ACTIONS, client_detail
from .rbac import Forbidden, require_super_admin
from .roles import Role
from .store import ControlPlaneStore


def assert_action_allowed(action: str) -> None:
    if action in FORBIDDEN_ADMIN_ACTIONS:
        raise Forbidden(f"action_forbidden:{action}")
    if action not in ALLOWED_ADMIN_ACTIONS:
        raise Forbidden(f"action_unknown:{action}")


def admin_view_client(store: ControlPlaneStore, actor_id: str, client_id: str,
                      *, telemetry: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("view")
    if client_id not in store.accounts or store.accounts[client_id].role != Role.CLIENT:
        raise Forbidden("unknown_client")
    store.audit_log(actor_id, "ADMIN_CLIENT_VIEWED", client_id, "ok")
    return client_detail(store, client_id, telemetry=telemetry)


def admin_disable_client(store: ControlPlaneStore, actor_id: str, client_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("disable_client")
    acc = store.disable_account(client_id, actor=actor_id)
    return {"client_id": acc.id, "status": acc.status.value, "effect": "STOP_NEW_ORDERS_THEN_SAFE_MODE"}


def admin_enable_client(store: ControlPlaneStore, actor_id: str, client_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("enable_client")
    acc = store.enable_account(client_id, actor=actor_id)
    return {"client_id": acc.id, "status": acc.status.value}


def admin_revoke_license(store: ControlPlaneStore, actor_id: str, license_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("revoke_license")
    lic = store.revoke_license(license_id, actor=actor_id)
    return {"license_id": lic.id, "status": lic.status.value, "effect": "LICENSE_BLOCKED_AFTER_RECONCILE"}


def admin_disable_license(store: ControlPlaneStore, actor_id: str, license_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("disable_license")
    lic = store.disable_license(license_id, actor=actor_id)
    return {"license_id": lic.id, "status": lic.status.value}


def admin_generate_license(
    store: ControlPlaneStore, actor_id: str, client_id: str, *, expires_at: Optional[str] = None,
) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("generate_license")
    lic = store.issue_license(client_id, expires_at=expires_at, actor=actor_id)
    return {"license_id": lic.id, "status": lic.status.value, "expires_at": lic.expires_at}


def admin_disable_device(store: ControlPlaneStore, actor_id: str, device_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("disable_device")
    dev = store.disable_device(device_id, actor=actor_id)
    return {"device_id": dev.id, "status": dev.status.value, "effect": "STOP_NEW_ORDERS_THEN_SAFE_MODE"}


def admin_revoke_device(store: ControlPlaneStore, actor_id: str, device_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("revoke_device")
    dev = store.revoke_device(device_id, actor=actor_id)
    return {"device_id": dev.id, "status": dev.status.value, "effect": "BLOCKED_AFTER_RECONCILE"}


def admin_revoke_session(store: ControlPlaneStore, actor_id: str, session_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    assert_action_allowed("revoke_session")
    store.revoke_session(session_id, actor=actor_id)
    return {"session_id": session_id, "revoked": True}
