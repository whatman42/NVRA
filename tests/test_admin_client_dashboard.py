"""Admin client dashboard: SUPER_ADMIN sees all clients; tenant isolation; no forbidden actions."""
from __future__ import annotations

import time

import pytest

from god.control_plane import (
    ALLOWED_ADMIN_ACTIONS,
    FORBIDDEN_ADMIN_ACTIONS,
    ControlPlaneStore,
    Forbidden,
    Role,
    admin_client_detail,
    admin_clients,
    admin_clients_summary,
    admin_disable_client,
    admin_disable_device,
    admin_generate_license,
    admin_revoke_license,
    admin_view_client,
    client_portfolio,
    client_status,
)
from god.control_plane.api import admin_clients as api_admin_clients
from god.control_plane.dashboard import derive_connection_status


def _seed():
    store = ControlPlaneStore()
    admin = store.create_account("root", Role.SUPER_ADMIN)
    a = store.create_account("alice", Role.CLIENT)
    b = store.create_account("bob", Role.CLIENT)
    la = store.issue_license(a.id, actor=admin.id)
    lb = store.issue_license(b.id, actor=admin.id)
    da = store.register_device(a.id, client_version="1.2.0", os_name="Windows")
    db = store.register_device(b.id, client_version="1.1.0", os_name="Linux")
    store.record_heartbeat(
        account_id=a.id, device_id=da.id, license_id=la.id,
        client_version="1.2.0", status="OK", state_hash="h1", runtime_status="PAPER",
    )
    return store, admin, a, b, la, lb, da, db


def test_admin_sees_all_clients():
    store, admin, a, b, *_ = _seed()
    rows = admin_clients(store, admin.id)
    assert len(rows) == 2
    ids = {r["client_id"] for r in rows}
    assert a.id in ids and b.id in ids


def test_client_cannot_list_admin_clients():
    store, admin, a, b, *_ = _seed()
    with pytest.raises(Forbidden):
        api_admin_clients(store, a.id)


def test_admin_client_detail_no_secrets():
    store, admin, a, *_ = _seed()
    detail = admin_view_client(
        store, admin.id, a.id,
        telemetry={
            "equity": 1000.0, "balance": 1000.0, "api_key": "SHOULD_NOT_APPEAR",
            "password": "x", "risk_governor": "NORMAL", "active_model": "m1",
            "model_version": "1", "cpu": 0.2, "ram": 0.4,
        },
    )
    raw = str(detail)
    assert "SHOULD_NOT_APPEAR" not in raw
    assert "api_key" not in detail
    assert detail["portfolio_summary"]["equity"] == 1000.0
    assert detail["risk_status"]["governor"] == "NORMAL"
    assert detail["model_status"]["active_model"] == "m1"
    assert detail["admin_capabilities"]["bypass_risk_governor"] is False
    assert detail["runtime"]["mode"] == "PAPER"


def test_tenant_isolation_portfolio():
    store, admin, a, b, *_ = _seed()
    # Client A forges client_id=B → still scoped to A
    scoped = client_portfolio(store, a.id, requested_client_id=b.id)
    assert scoped["client_id"] == a.id
    # Admin can request B
    assert client_portfolio(store, admin.id, requested_client_id=b.id)["client_id"] == b.id


def test_client_cannot_view_other_detail_via_admin_api():
    store, admin, a, b, *_ = _seed()
    with pytest.raises(Forbidden):
        admin_client_detail(store, a.id, b.id)


def test_client_cannot_admin_view_other():
    store, admin, a, b, *_ = _seed()
    with pytest.raises(Forbidden):
        admin_view_client(store, a.id, b.id)


def test_dashboard_summary_counts():
    store, admin, a, b, *_ = _seed()
    summary = admin_clients_summary(store, admin.id)
    assert summary["clients_total"] == 2
    assert summary["online"] >= 1


def test_status_derivation_real_state():
    assert derive_connection_status(
        license_status="REVOKED", account_status="ACTIVE", last_hb_age=10, safe_mode=False
    ) == "LICENSE_BLOCKED"
    assert derive_connection_status(
        license_status="ACTIVE", account_status="ACTIVE", last_hb_age=10, safe_mode=True
    ) == "SAFE_MODE"
    assert derive_connection_status(
        license_status="ACTIVE", account_status="ACTIVE", last_hb_age=10, safe_mode=False
    ) == "ONLINE"
    assert derive_connection_status(
        license_status="ACTIVE", account_status="ACTIVE", last_hb_age=600, safe_mode=False
    ) == "OFFLINE_GRACE"


def test_admin_actions_audited():
    store, admin, a, b, la, lb, da, db = _seed()
    admin_disable_client(store, admin.id, a.id)
    assert any(e.action == "CLIENT_DISABLED" for e in store.audit)
    admin_generate_license(store, admin.id, b.id, expires_at=None)
    assert any(e.action == "LICENSE_CREATED" for e in store.audit)
    admin_revoke_license(store, admin.id, lb.id)
    assert any(e.action == "LICENSE_REVOKED" for e in store.audit)
    admin_disable_device(store, admin.id, da.id)
    assert any(e.action == "DEVICE_DISABLED" for e in store.audit)


def test_forbidden_actions_constant():
    assert "bypass_risk_governor" in FORBIDDEN_ADMIN_ACTIONS
    assert "force_live_order" in FORBIDDEN_ADMIN_ACTIONS
    assert "view" in ALLOWED_ADMIN_ACTIONS
    assert "revoke_license" in ALLOWED_ADMIN_ACTIONS


def test_heartbeat_timeout_not_auto_revoke():
    store, admin, a, b, la, lb, da, db = _seed()
    store.heartbeats[-1].timestamp = time.time() - 10_000
    row = admin_clients(store, admin.id)[0]
    assert row["heartbeat_class"] in {"CLIENT_OFFLINE", "OK", "SAFE_MODE"}
    assert row["license_status"] == "ACTIVE"
