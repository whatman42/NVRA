"""EA Auto-Installer — Phase 3B-B.

Idempotent atomic deploy of thin NUNG Bridge EA into terminal Experts folder.
No trading intelligence.
"""

from .models import DeploymentRecord, InstallResult, InstallAction
from .installer import EAInstaller
from .errors import InstallerError, ArtifactNotFoundError, ExpertsPathError

__all__ = [
    "DeploymentRecord",
    "InstallResult",
    "InstallAction",
    "EAInstaller",
    "InstallerError",
    "ArtifactNotFoundError",
    "ExpertsPathError",
]
