"""Phase 6H — N.U.N.G. / NVRA final release models. READY ≠ LIVE."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.research.provenance import content_hash


class ReleaseReadiness(str, Enum):
    NOT_READY = "NOT_READY"
    READY_PAPER = "READY_PAPER"
    READY_SHADOW = "READY_SHADOW"
    READY_PRODUCTION = "READY_PRODUCTION"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ComponentCheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


SCHEMA_VERSION = "release-6h-v1"

# Public product identity
PRODUCT_BRAND = "NVRA"
CREATOR_IDENTITY = "N.U.N.G."
CONTACT_PHONE = "+628981555380"
PAYMENT_METHODS = ("GoPay", "OVO", "DANA", "ShopeePay")


@dataclass(frozen=True)
class ComponentCheck:
    name: str
    status: ComponentCheckStatus
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status.value, "detail": self.detail}


@dataclass(frozen=True)
class ModelStatus:
    model_name: str = "none"
    model_version: str = "0"
    model_type: str = "none"
    status: str = "inactive"
    activated_at: str = ""
    champion_since: str = ""
    training_timestamp: str = ""
    fingerprint: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_type": self.model_type,
            "status": self.status,
            "activated_at": self.activated_at,
            "champion_since": self.champion_since,
            "training_timestamp": self.training_timestamp,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class UniverseStatus:
    active_pairs: tuple[str, ...] = ()
    pair_count: int = 0
    equity: Optional[float] = None
    currency: str = "USD"
    exposure: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_pairs": list(self.active_pairs),
            "pair_count": self.pair_count,
            "equity": self.equity,
            "currency": self.currency,
            "exposure": self.exposure,
        }


@dataclass(frozen=True)
class GuiStatusContract:
    """Read-only status for future NVRA GUI. No trading controls."""

    product_brand: str = PRODUCT_BRAND
    creator: str = CREATOR_IDENTITY
    contact: str = CONTACT_PHONE
    payment_methods: tuple[str, ...] = PAYMENT_METHODS
    system_state: str = "STOPPED"  # WORKING | STOPPED | ATTENTION
    brain: str = "Stopped"
    memory: str = "Unknown"
    research: str = "Unknown"
    learning: str = "Unknown"
    risk_engine: str = "Unknown"
    market_data: str = "Unknown"
    execution: str = "Blocked"
    mt4_bridge: str = "Not configured"
    mt5_bridge: str = "Not configured"
    database: str = "Unknown"
    security: str = "Unknown"
    model: Optional[ModelStatus] = None
    universe: Optional[UniverseStatus] = None
    safety_state: str = "fail_closed"
    notes: str = "gui_contract_read_only_no_trade_buttons"

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_brand": self.product_brand,
            "creator": self.creator,
            "contact": self.contact,
            "payment_methods": list(self.payment_methods),
            "system_state": self.system_state,
            "brain": self.brain,
            "memory": self.memory,
            "research": self.research,
            "learning": self.learning,
            "risk_engine": self.risk_engine,
            "market_data": self.market_data,
            "execution": self.execution,
            "mt4_bridge": self.mt4_bridge,
            "mt5_bridge": self.mt5_bridge,
            "database": self.database,
            "security": self.security,
            "model": self.model.to_dict() if self.model else None,
            "universe": self.universe.to_dict() if self.universe else None,
            "safety_state": self.safety_state,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReleaseManifest:
    readiness: ReleaseReadiness
    checks: tuple[ComponentCheck, ...]
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    product_brand: str = PRODUCT_BRAND
    creator: str = CREATOR_IDENTITY
    live_trading_enabled: bool = False
    headless_capable: bool = True
    gui_optional: bool = True
    notes: str = "final_release_gate_pre_live"

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness": self.readiness.value,
            "checks": [c.to_dict() for c in self.checks],
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "product_brand": self.product_brand,
            "creator": self.creator,
            "live_trading_enabled": self.live_trading_enabled,
            "headless_capable": self.headless_capable,
            "gui_optional": self.gui_optional,
            "notes": self.notes,
        }


def make_manifest_hash(payload: dict[str, Any]) -> str:
    return content_hash(payload)
