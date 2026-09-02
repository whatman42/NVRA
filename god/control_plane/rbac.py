"""Server-side RBAC and tenant isolation."""
from __future__ import annotations
from .roles import Role
from .store import ControlPlaneStore

class Forbidden(Exception):
    pass

def require_super_admin(store: ControlPlaneStore, account_id: str) -> None:
    acc = store.accounts.get(account_id)
    if not acc or acc.role != Role.SUPER_ADMIN:
        raise Forbidden("super_admin_required")

def require_self_or_admin(store: ControlPlaneStore, actor_id: str, target_account_id: str) -> None:
    actor = store.accounts.get(actor_id)
    if not actor:
        raise Forbidden("unknown_actor")
    if actor.role == Role.SUPER_ADMIN:
        return
    if actor.id != target_account_id:
        raise Forbidden("cross_tenant_denied")

def client_portfolio_scope(store: ControlPlaneStore, actor_id: str, requested_client_id: str | None) -> str:
    actor = store.accounts.get(actor_id)
    if not actor:
        raise Forbidden("unknown_actor")
    if actor.role == Role.SUPER_ADMIN:
        if not requested_client_id:
            raise Forbidden("client_id_required_for_admin")
        if requested_client_id not in store.accounts:
            raise Forbidden("unknown_client")
        return requested_client_id
    return actor.id
