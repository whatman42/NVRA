"""NUNG single-executable application shell.

Modes: TRIAL | CLIENT | ADMIN (KeyGen is ADMIN CONTROL function, not a separate EXE).

Admin is determined by cryptographic root-admin record + role — NEVER by username alone.
LIVE capital remains BLOCKED by default.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from god.auth import UserRegistry, SessionStore, UserIdentity
from god.auth.session import SessionError
from god.mt5_runtime import detect_mt5, LiveCapitalGate
from god.mt5_runtime.states import TerminalSnapshot
from god.persist import save_bundle, load_bundle, verify_bundle_owner, ExportError
from god.admin import AdminApplication

from .modes import AppMode, Role, capabilities_for, is_admin_role
from .root_admin import RootAdminStore


class AppStatus(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    SAFE_STOP = "SAFE_STOP"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TRIAL = "TRIAL"
    NEEDS_ROOT_ADMIN = "NEEDS_ROOT_ADMIN"


@dataclass
class AppState:
    status: AppStatus = AppStatus.AUTH_REQUIRED
    mode: AppMode = AppMode.TRIAL
    role: Role = Role.NONE
    identity: Optional[UserIdentity] = None
    session_token: Optional[str] = None
    mt5: Optional[TerminalSnapshot] = None
    last_error: str = ""
    cycle_count: int = 0
    broker_orders_submitted: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "mode": self.mode.value,
            "role": self.role.value,
            "username": self.identity.username if self.identity else None,
            "display_name": self.identity.display_name if self.identity else None,
            "mt5": self.mt5.to_dict() if self.mt5 else None,
            "last_error": self.last_error,
            "cycle_count": self.cycle_count,
            "broker_orders_submitted": self.broker_orders_submitted,
            "live_capital": "BLOCKED",
            "capabilities": sorted(capabilities_for(self.mode)),
        }


class NungApplication:
    """Single NUNG.exe controller: Trial / Client / Admin modes."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.registry = UserRegistry(self.data_dir / "users.json")
        self.sessions = SessionStore()
        self.live_gate = LiveCapitalGate(blocked=True)
        self.root_admins = RootAdminStore(self.data_dir / "root_admin.json")
        # Admin control plane reuses TAHAP 9 AdminApplication storage under same data_dir
        self.admin_plane = AdminApplication(self.data_dir / "admin_plane")
        self.state = AppState()
        self._running = False
        if not self.root_admins.exists():
            self.state.status = AppStatus.NEEDS_ROOT_ADMIN

    # ----- Trial (no login) -----

    def start_trial(self) -> Dict[str, Any]:
        """DEMO/PAPER only. No admin, no client data access, no LIVE."""
        self.state.mode = AppMode.TRIAL
        self.state.role = Role.NONE
        self.state.identity = None
        self.state.session_token = None
        self.state.status = AppStatus.TRIAL
        self._running = True
        self.refresh_mt5()
        self.live_gate.assert_no_live_orders()
        return {
            "ok": True,
            "mode": AppMode.TRIAL.value,
            "live_capital": "BLOCKED",
            "capabilities": sorted(capabilities_for(AppMode.TRIAL)),
            "broker_orders_submitted": 0,
        }

    # ----- Root admin bootstrap -----

    def needs_root_admin(self) -> bool:
        return not self.root_admins.exists()

    def initialize_root_admin(
        self, username: str, password: str, display_name: str = ""
    ) -> Dict[str, Any]:
        result = self.root_admins.initialize(username, password, display_name=display_name)
        if result.get("ok"):
            self.state.status = AppStatus.AUTH_REQUIRED
        return result

    # ----- Client -----

    def register_client(
        self, username: str, password: str, display_name: str = ""
    ) -> Dict[str, Any]:
        """REGISTER always creates CLIENT role — cannot self-promote to admin."""
        result = self.registry.register(username, password, display_name=display_name or None)
        if not result.ok:
            return {"ok": False, "reason": result.reason}
        return {
            "ok": True,
            "user_id": result.identity.user_id if result.identity else None,
            "role": Role.CLIENT.value,
        }

    def register(self, username: str, password: str, display_name: str = "") -> Dict[str, Any]:
        """Backward-compatible alias — always CLIENT."""
        return self.register_client(username, password, display_name)

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Try root-admin first (role from crypto record), else client registry."""
        # Admin path: cryptographic root record — NOT username=="admin"
        root = self.root_admins.authenticate(username, password)
        if root is not None:
            identity = UserIdentity(
                user_id=root.admin_id,
                username=root.username,
                display_name=root.display_name,
                created_at=root.created_at,
                public_binding=root.public_key_id,
            )
            session = self.sessions.create(identity)
            self.state.identity = identity
            self.state.session_token = session.token
            self.state.mode = AppMode.ADMIN
            self.state.role = Role(root.role) if root.role in Role._value2member_map_ else Role.ROOT_ADMIN
            self.state.status = AppStatus.STOPPED
            return {
                "ok": True,
                "token": session.token,
                "mode": AppMode.ADMIN.value,
                "role": self.state.role.value,
                "display_name": identity.display_name,
                "user_id": identity.user_id,
            }

        identity = self.registry.authenticate(username, password)
        if identity is None:
            self.state.status = AppStatus.AUTH_REQUIRED
            return {"ok": False, "reason": "invalid_credentials"}
        session = self.sessions.create(identity)
        self.state.identity = identity
        self.state.session_token = session.token
        self.state.mode = AppMode.CLIENT
        self.state.role = Role.CLIENT
        self.state.status = AppStatus.STOPPED
        return {
            "ok": True,
            "token": session.token,
            "mode": AppMode.CLIENT.value,
            "role": Role.CLIENT.value,
            "display_name": identity.display_name,
            "user_id": identity.user_id,
        }

    def require_auth(self, token: str) -> UserIdentity:
        return self.sessions.require(token).identity

    def require_admin(self, token: str) -> UserIdentity:
        session = self.sessions.require(token)
        if self.state.mode != AppMode.ADMIN or not is_admin_role(self.state.role):
            # Also verify token identity matches root admin record
            root = self.root_admins.load()
            if root is None or session.identity.user_id != root.admin_id:
                raise SessionError("admin_authorization_required")
        return session.identity

    # ----- Runtime -----

    def refresh_mt5(self) -> TerminalSnapshot:
        result = detect_mt5()
        self.state.mt5 = result.snapshot
        return result.snapshot

    def start(self, token: Optional[str] = None) -> Dict[str, Any]:
        if self.state.mode == AppMode.TRIAL and token is None:
            return self.start_trial()
        if token is None:
            return {"ok": False, "reason": "token_required"}
        try:
            identity = self.require_auth(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        self.state.identity = identity
        self.refresh_mt5()
        self._running = True
        self.state.status = AppStatus.RUNNING
        self.live_gate.assert_no_live_orders()
        # Client trading gated by license when not trial
        trading_ok = True
        if self.state.mode == AppMode.CLIENT:
            trading_ok = self.admin_plane.licenses.trading_allowed_for_user(identity.user_id)
        return {
            "ok": True,
            "status": self.state.status.value,
            "mode": self.state.mode.value,
            "role": self.state.role.value,
            "trading_allowed": trading_ok if self.state.mode != AppMode.TRIAL else False,
            "mt5": self.state.mt5.to_dict() if self.state.mt5 else None,
            "live_capital": "BLOCKED",
            "broker_orders_submitted": self.live_gate.broker_orders_submitted,
        }

    def stop(self, token: Optional[str] = None) -> Dict[str, Any]:
        if self.state.mode != AppMode.TRIAL:
            if token is None:
                return {"ok": False, "reason": "token_required"}
            try:
                self.require_auth(token)
            except SessionError as e:
                return {"ok": False, "reason": str(e)}
        self._running = False
        self.state.status = AppStatus.SAFE_STOP
        self.live_gate.assert_no_live_orders()
        return {
            "ok": True,
            "status": self.state.status.value,
            "broker_orders_submitted": self.live_gate.broker_orders_submitted,
        }

    def save_state(self, token: str, path: Path, **payload: Any) -> Dict[str, Any]:
        if self.state.mode == AppMode.TRIAL:
            return {"ok": False, "reason": "trial_cannot_save_client_data"}
        try:
            identity = self.require_auth(token)
            save_bundle(path, identity, **payload)
            return {"ok": True}
        except (SessionError, ExportError, OSError) as e:
            return {"ok": False, "reason": str(e)}

    def load_state(self, token: str, path: Path) -> Dict[str, Any]:
        if self.state.mode == AppMode.TRIAL:
            return {"ok": False, "reason": "trial_cannot_load_client_data"}
        try:
            identity = self.require_auth(token)
            bundle = load_bundle(path)
            verify_bundle_owner(bundle, identity)
            return {"ok": True, "owner": bundle.owner_username, "created_at": bundle.created_at}
        except (SessionError, ExportError) as e:
            return {"ok": False, "reason": str(e)}

    def dashboard(self) -> Dict[str, Any]:
        if self.state.mt5 is None:
            self.refresh_mt5()
        return self.state.to_dict()

    # ----- Admin control (inside NUNG.exe — not separate KeyGen.exe) -----

    def admin_create_license(
        self,
        token: str,
        *,
        user_id: str,
        username: str,
        expires_in_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            admin = self.require_admin(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        kp = self.root_admins.signing_keypair()
        if kp is not None:
            self.admin_plane.licenses.keypair = kp
        rec = self.admin_plane.licenses.create(
            user_id=user_id, username=username, expires_in_days=expires_in_days
        )
        self.admin_plane.audit.record(
            actor_id=admin.user_id,
            target_id=user_id,
            action="LICENSE_CREATED",
            result="SUCCESS",
            details={"license_id": rec.license_id},
        )
        return {"ok": True, "license": rec.to_dict()}

    def admin_list_clients(self, token: str) -> Dict[str, Any]:
        try:
            self.require_admin(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        clients = []
        for key, rec in self.registry._users.items():
            ident = rec.get("identity") or {}
            uid = ident.get("user_id", "")
            trading = self.admin_plane.licenses.trading_allowed_for_user(uid)
            clients.append(
                {
                    "username": ident.get("username"),
                    "user_id": uid,
                    "role": Role.CLIENT.value,
                    "trading_allowed": trading,
                }
            )
        return {"ok": True, "clients": clients}
