"""Framework-agnostic control-plane API handlers. No order endpoints."""
from __future__ import annotations
from typing import Any, Optional
from .dashboard import admin_list_clients, client_detail
from .rbac import Forbidden, client_portfolio_scope, require_self_or_admin, require_super_admin
from .store import ControlPlaneStore

def health() -> dict[str, str]:
    return {"status": "ok", "service": "nvra-control-plane"}

def admin_list_accounts(store: ControlPlaneStore, actor_id: str) -> list[dict[str, Any]]:
    require_super_admin(store, actor_id)
    return [a.to_dict() for a in store.accounts.values()]

def admin_clients(store: ControlPlaneStore, actor_id: str) -> list[dict[str, Any]]:
    require_super_admin(store, actor_id)
    return admin_list_clients(store)

def admin_client_detail(store: ControlPlaneStore, actor_id: str, client_id: str) -> dict[str, Any]:
    require_super_admin(store, actor_id)
    return client_detail(store, client_id)

def client_me(store: ControlPlaneStore, actor_id: str) -> dict[str, Any]:
    acc = store.accounts.get(actor_id)
    if not acc:
        raise Forbidden("unknown_actor")
    return acc.to_dict()

def client_status(store: ControlPlaneStore, actor_id: str) -> dict[str, Any]:
    require_self_or_admin(store, actor_id, actor_id)
    return client_detail(store, actor_id)

def client_portfolio(store: ControlPlaneStore, actor_id: str, requested_client_id: Optional[str] = None) -> dict[str, Any]:
    scoped = client_portfolio_scope(store, actor_id, requested_client_id)
    return {"client_id": scoped, "mode": "PAPER", "equity": None, "note": "portfolio_from_telemetry_only"}
