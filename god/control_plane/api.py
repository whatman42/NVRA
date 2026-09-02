"""Framework-agnostic control-plane API handlers. No order endpoints. No secrets."""
from __future__ import annotations

from typing import Any, Optional

from .admin_actions import (
    admin_disable_client,
    admin_disable_device,
    admin_disable_license,
    admin_enable_client,
    admin_generate_license,
    admin_revoke_device,
    admin_revoke_license,
    admin_revoke_session,
    admin_view_client,
)
from .dashboard import admin_dashboard_summary, admin_list_clients, client_detail
from .rbac import Forbidden, client_portfolio_scope, require_self_or_admin, require_super_admin
from .store import ControlPlaneStore


def health() -> dict[str, str]:
    return {"status": "ok", "service": "nvra-control-plane"}


def admin_list_accounts(store: ControlPlaneStore, actor_id: str) -> list[dict[str, Any]]:
    require_super_admin(store, actor_id)
    return [a.to_dict() for a in store.accounts.values()]


def admin_clients(store: ControlPlaneStore, actor_id: str) -> list[dict[str, Any]]:
    """GET /api/v1/admin/clients — SUPER_ADMIN only."""
    require_super_admin(store, actor_id)
    return admin_list_clients(store)


def admin_clients_summary(store: ControlPlaneStore, actor_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    return admin_dashboard_summary(store)


def admin_client_detail(
    store: ControlPlaneStore, actor_id: str, client_id: str,
    *, telemetry: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """GET /api/v1/admin/clients/{client_id} — SUPER_ADMIN only."""
    return admin_view_client(store, actor_id, client_id, telemetry=telemetry)


def admin_action_disable_client(store: ControlPlaneStore, actor_id: str, client_id: str) -> dict[str, Any]:
    return admin_disable_client(store, actor_id, client_id)


def admin_action_enable_client(store: ControlPlaneStore, actor_id: str, client_id: str) -> dict[str, Any]:
    return admin_enable_client(store, actor_id, client_id)


def admin_action_revoke_license(store: ControlPlaneStore, actor_id: str, license_id: str) -> dict[str, Any]:
    return admin_revoke_license(store, actor_id, license_id)


def admin_action_disable_license(store: ControlPlaneStore, actor_id: str, license_id: str) -> dict[str, Any]:
    return admin_disable_license(store, actor_id, license_id)


def admin_action_generate_license(
    store: ControlPlaneStore, actor_id: str, client_id: str, *, expires_at: Optional[str] = None,
) -> dict[str, Any]:
    return admin_generate_license(store, actor_id, client_id, expires_at=expires_at)


def admin_action_disable_device(store: ControlPlaneStore, actor_id: str, device_id: str) -> dict[str, Any]:
    return admin_disable_device(store, actor_id, device_id)


def admin_action_revoke_device(store: ControlPlaneStore, actor_id: str, device_id: str) -> dict[str, Any]:
    return admin_revoke_device(store, actor_id, device_id)


def admin_action_revoke_session(store: ControlPlaneStore, actor_id: str, session_id: str) -> dict[str, Any]:
    return admin_revoke_session(store, actor_id, session_id)


def client_me(store: ControlPlaneStore, actor_id: str) -> dict[str, Any]:
    """GET /api/v1/client/me"""
    acc = store.accounts.get(actor_id)
    if not acc:
        raise Forbidden("unknown_actor")
    return acc.to_dict()


def client_status(store: ControlPlaneStore, actor_id: str) -> dict[str, Any]:
    """GET /api/v1/client/status — always scoped to actor."""
    require_self_or_admin(store, actor_id, actor_id)
    return client_detail(store, actor_id)


def client_portfolio(
    store: ControlPlaneStore, actor_id: str, requested_client_id: Optional[str] = None,
) -> dict[str, Any]:
    """GET /api/v1/client/portfolio — ignores forged client_id for CLIENT role."""
    scoped = client_portfolio_scope(store, actor_id, requested_client_id)
    return {
        "client_id": scoped,
        "mode": "PAPER",
        "equity": None,
        "balance": None,
        "available_balance": None,
        "open_positions": None,
        "exposure": None,
        "pnl": None,
        "drawdown": None,
        "risk_state": "NORMAL",
        "note": "portfolio_from_telemetry_only",
    }
