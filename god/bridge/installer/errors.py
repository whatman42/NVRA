"""Installer errors."""

from __future__ import annotations

from god.bridge.errors import BridgeError


class InstallerError(BridgeError):
    """Base installer error."""


class ArtifactNotFoundError(InstallerError):
    """Bundled or source EA artifact not found."""


class ExpertsPathError(InstallerError):
    """Experts directory missing or not writable."""


class IntegrityInstallError(InstallerError):
    """Post-install integrity verification failed."""
