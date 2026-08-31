"""Phase 6H — N.U.N.G. / NVRA Final Production Release Gate.

Product brand: NVRA
Creator identity: N.U.N.G.
READY ≠ LIVE · ALLOW ≠ OPEN · GUI optional · headless-first
"""

from .models import (
    CREATOR_IDENTITY,
    PRODUCT_BRAND,
    ComponentCheck,
    ComponentCheckStatus,
    GuiStatusContract,
    ModelStatus,
    ReleaseManifest,
    ReleaseReadiness,
    UniverseStatus,
)
from .readiness import FinalReleaseGate

__all__ = [
    "PRODUCT_BRAND",
    "CREATOR_IDENTITY",
    "ComponentCheck",
    "ComponentCheckStatus",
    "GuiStatusContract",
    "ModelStatus",
    "ReleaseManifest",
    "ReleaseReadiness",
    "UniverseStatus",
    "FinalReleaseGate",
]
