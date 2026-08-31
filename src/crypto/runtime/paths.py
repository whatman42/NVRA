"""Deterministic path resolution — never trust os.getcwd() as source of truth.

Deployment modes
----------------
PORTABLE:  ``.portable`` marker next to CRYPTO.exe → all writable data under app root.
INSTALLED: no marker → program in install dir; user data under %LOCALAPPDATA%/CRYPTO
           (or ~/.local/share/CRYPTO on non-Windows).
DEV:       repository root; data under repo (or CRYPTO_HOME).
"""

from __future__ import annotations

import os
import sys
from enum import Enum, auto
from pathlib import Path

PORTABLE_MARKER = ".portable"


class DeployMode(Enum):
    DEV = auto()
    PORTABLE = auto()
    INSTALLED = auto()


def is_frozen() -> bool:
    """True when running under PyInstaller / frozen executable."""
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def application_root() -> Path:
    """Directory containing CRYPTO.exe (frozen) or repository root (dev)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
        if (parent / "src" / "crypto").is_dir() and (parent / "README.md").is_file():
            return parent
    return Path(__file__).resolve().parents[3]


def bundle_root() -> Path:
    """PyInstaller extraction / internal bundle directory."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return application_root()


def env_override_root() -> Path | None:
    """Optional CRYPTO_HOME for portable/test isolation."""
    val = os.environ.get("CRYPTO_HOME")
    if val:
        return Path(val).expanduser().resolve()
    return None


def detect_deploy_mode(app_root: Path | None = None) -> DeployMode:
    root = (app_root or application_root()).resolve()
    # Portable marker always wins for that directory
    if (root / PORTABLE_MARKER).is_file() or (root / PORTABLE_MARKER).is_dir():
        return DeployMode.PORTABLE
    if is_frozen():
        return DeployMode.INSTALLED
    return DeployMode.DEV


def user_data_root(app_root: Path | None = None, mode: DeployMode | None = None) -> Path:
    """Writable user-data root (never under Program Files or _MEIPASS)."""
    root = (app_root or application_root()).resolve()
    mode = mode or detect_deploy_mode(root)
    # CRYPTO_HOME is a full data-root override for DEV/test isolation
    if mode is DeployMode.DEV:
        override = env_override_root()
        if override is not None:
            return override
        return root
    if mode is DeployMode.PORTABLE:
        return root
    # INSTALLED — prefer LOCALAPPDATA when set (including tests on Linux)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base).expanduser().resolve() / "CRYPTO"
    if sys.platform != "win32":
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            return Path(xdg).expanduser().resolve() / "CRYPTO"
        return Path.home().resolve() / ".local" / "share" / "CRYPTO"
    return Path.home().resolve() / "AppData" / "Local" / "CRYPTO"


class PathResolver:
    """Central absolute-path authority for program + user data."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        mode: DeployMode | None = None,
        data_root: Path | None = None,
    ) -> None:
        self.program_root = (root or application_root()).resolve()
        self.mode = mode if mode is not None else detect_deploy_mode(self.program_root)
        if data_root is not None:
            self.root = data_root.resolve()
        else:
            self.root = user_data_root(self.program_root, self.mode).resolve()
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        for name in (
            "data",
            "models",
            "registry",
            "state",
            "cache",
            "logs",
            "audit",
            "backups",
        ):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        # resources may live in program/bundle only
        res = self.program_root / "resources"
        if not res.exists() and not is_frozen():
            res.mkdir(parents=True, exist_ok=True)

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def models_dir(self) -> Path:
        return self.root / "models"

    @property
    def registry_dir(self) -> Path:
        return self.root / "registry"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def audit_dir(self) -> Path:
        return self.root / "audit"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @property
    def resources_dir(self) -> Path:
        bundled = bundle_root() / "resources"
        if bundled.is_dir():
            return bundled
        prog = self.program_root / "resources"
        if prog.is_dir():
            return prog
        return self.root / "resources"

    def sqlite_path(self, name: str = "crypto.db") -> Path:
        """User-data SQLite — never under _MEIPASS or Program Files."""
        return self.state_dir / name

    def log_file(self, name: str = "crypto.log") -> Path:
        return self.logs_dir / name

    def as_dict(self) -> dict[str, str]:
        return {
            "mode": self.mode.name,
            "program_root": str(self.program_root),
            "data_root": str(self.root),
            "frozen": str(is_frozen()),
            "data": str(self.data_dir),
            "models": str(self.models_dir),
            "registry": str(self.registry_dir),
            "state": str(self.state_dir),
            "cache": str(self.cache_dir),
            "logs": str(self.logs_dir),
            "audit": str(self.audit_dir),
            "backups": str(self.backups_dir),
            "resources": str(self.resources_dir),
        }


_RESOLVER: PathResolver | None = None


def get_resolver() -> PathResolver:
    global _RESOLVER
    if _RESOLVER is None:
        _RESOLVER = PathResolver()
    return _RESOLVER


def set_resolver(resolver: PathResolver) -> None:
    global _RESOLVER
    _RESOLVER = resolver


def write_portable_marker(directory: Path) -> Path:
    """Create portable edition marker."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / PORTABLE_MARKER
    marker.write_text(
        "CRYPTO portable edition\n"
        "User data is stored next to CRYPTO.exe.\n"
        "Do not delete this file.\n",
        encoding="utf-8",
    )
    return marker
