"""NUNG runtime modes — single executable, three modes.

Admin is NEVER determined by username string.
"""
from __future__ import annotations

from enum import Enum


class AppMode(str, Enum):
    """Operational mode inside NUNG.exe."""

    TRIAL = "TRIAL"  # demo/paper only, no admin, no client data
    CLIENT = "CLIENT"  # authenticated client
    ADMIN = "ADMIN"  # authenticated admin via cryptographic identity + role


class Role(str, Enum):
    """Authorization role — assigned at identity creation, not by username."""

    NONE = "NONE"
    CLIENT = "CLIENT"
    ADMIN = "ADMIN"
    ROOT_ADMIN = "ROOT_ADMIN"


# Capabilities by mode (documentation + runtime checks)
TRIAL_CAPABILITIES = frozenset(
    {
        "paper_trading",
        "local_ml_inference",
        "mt5_detect_readonly",
        "dashboard_limited",
    }
)

CLIENT_CAPABILITIES = frozenset(
    {
        "paper_trading",
        "local_ml",
        "save_load",
        "chat",
        "voice_notify",
        "mt5_detect",
        "dashboard",
        "heartbeat",
    }
)

ADMIN_CAPABILITIES = frozenset(
    {
        "client_management",
        "license_keygen",
        "device_management",
        "session_management",
        "account_recovery",
        "audit",
        "monitoring",
        "chat",
        "admin_dashboard",
    }
)


def capabilities_for(mode: AppMode) -> frozenset:
    if mode == AppMode.TRIAL:
        return TRIAL_CAPABILITIES
    if mode == AppMode.CLIENT:
        return CLIENT_CAPABILITIES
    if mode == AppMode.ADMIN:
        return ADMIN_CAPABILITIES | CLIENT_CAPABILITIES
    return frozenset()


def is_admin_role(role: Role) -> bool:
    return role in (Role.ADMIN, Role.ROOT_ADMIN)
