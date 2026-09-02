"""NVRA Control Plane — license, devices, sessions, signed offline fallback, admin dashboard."""
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
from .api import (
    admin_client_detail,
    admin_clients,
    admin_clients_summary,
    client_me,
    client_portfolio,
    client_status,
    health,
)
from .dashboard import (
    ALLOWED_ADMIN_ACTIONS,
    FORBIDDEN_ADMIN_ACTIONS,
    admin_dashboard_summary,
    admin_list_clients,
    client_detail,
    derive_connection_status,
)
from .ed25519_license import LicenseKeyPair, build_license_payload, verify_license_payload
from .fallback import FallbackStore, OfflineDecision, SignedFallbackState, evaluate_offline
from .license_gate import GateResult, LicenseGate
from .models import Account, Device, License, Session
from .rbac import Forbidden
from .roles import AccountStatus, DeviceStatus, LicenseStatus, Role
from .store import ControlPlaneStore

__all__ = [
    "LicenseKeyPair", "build_license_payload", "verify_license_payload",
    "ControlPlaneStore", "LicenseGate", "GateResult",
    "FallbackStore", "SignedFallbackState", "OfflineDecision", "evaluate_offline",
    "Role", "AccountStatus", "DeviceStatus", "LicenseStatus",
    "Account", "License", "Device", "Session", "Forbidden",
    "health", "admin_clients", "admin_clients_summary", "admin_client_detail",
    "client_me", "client_status", "client_portfolio",
    "admin_list_clients", "admin_dashboard_summary", "client_detail",
    "derive_connection_status", "ALLOWED_ADMIN_ACTIONS", "FORBIDDEN_ADMIN_ACTIONS",
    "admin_view_client", "admin_disable_client", "admin_enable_client",
    "admin_revoke_license", "admin_disable_license", "admin_generate_license",
    "admin_disable_device", "admin_revoke_device", "admin_revoke_session",
]
