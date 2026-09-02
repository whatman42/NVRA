"""NVRA Control Plane — license, devices, sessions, signed offline fallback."""
from .api import admin_client_detail, admin_clients, client_me, client_portfolio, client_status, health
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
    "health", "admin_clients", "admin_client_detail",
    "client_me", "client_status", "client_portfolio",
]
