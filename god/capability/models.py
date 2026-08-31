"""Capability data models.

Every discovered capability is represented as a structured provider entry
so the agent can select the best provider for a given task without
hardcoded assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional
import time
import uuid


class CapabilityType(str, Enum):
    BROWSER = "browser"
    SHELL = "shell"
    VCS = "vcs"
    LANGUAGE_RUNTIME = "language_runtime"
    PACKAGE_MANAGER = "package_manager"
    ARCHIVE = "archive"
    CONTAINER = "container"
    VIRTUALIZATION = "virtualization"
    CLI_UTILITY = "cli_utility"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    HARDWARE = "hardware"
    OS = "os"
    SERVICE = "service"
    SCHEDULED_TASK = "scheduled_task"
    CERTIFICATE = "certificate"
    PROXY = "proxy"
    PYTHON = "python"
    COMPILER = "compiler"
    OTHER = "other"


@dataclass
class CapabilityProvider:
    """A concrete provider of a capability (e.g. Edge for browser)."""

    provider_id: str
    name: str
    capability: CapabilityType
    available: bool = False
    executable: Optional[str] = None
    version: Optional[str] = None
    path: Optional[str] = None
    interface: Optional[str] = None  # e.g. browser_automation, shell_exec
    health: str = "unknown"  # healthy | degraded | unavailable | unknown
    latency_ms: Optional[float] = None
    success_rate: float = 1.0
    last_checked: float = field(default_factory=time.time)
    last_used: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    failure_count: int = 0
    usage_count: int = 0

    @staticmethod
    def create(
        name: str,
        capability: CapabilityType,
        *,
        available: bool = False,
        executable: Optional[str] = None,
        version: Optional[str] = None,
        path: Optional[str] = None,
        interface: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "CapabilityProvider":
        return CapabilityProvider(
            provider_id=str(uuid.uuid4()),
            name=name,
            capability=capability,
            available=available,
            executable=executable,
            version=version,
            path=path or executable,
            interface=interface,
            health="healthy" if available else "unavailable",
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["capability"] = self.capability.value
        return d

    def mark_used(self, success: bool = True, latency_ms: Optional[float] = None) -> None:
        self.last_used = time.time()
        self.usage_count += 1
        if latency_ms is not None:
            self.latency_ms = latency_ms
        if success:
            # Exponential moving average toward 1.0
            self.success_rate = 0.9 * self.success_rate + 0.1
        else:
            self.failure_count += 1
            self.success_rate = 0.9 * self.success_rate
            if self.failure_count >= 3:
                self.health = "degraded"
            if self.failure_count >= 10:
                self.health = "unavailable"
                self.available = False


@dataclass
class Capability:
    """Logical capability with one or more providers."""

    capability: CapabilityType
    providers: list[CapabilityProvider] = field(default_factory=list)

    def best_provider(self) -> Optional[CapabilityProvider]:
        """Select the best available provider by health and success_rate."""
        available = [p for p in self.providers if p.available and p.health != "unavailable"]
        if not available:
            return None
        return max(
            available,
            key=lambda p: (p.health == "healthy", p.success_rate, -(p.latency_ms or 9999)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability.value,
            "providers": [p.to_dict() for p in self.providers],
            "best": self.best_provider().to_dict() if self.best_provider() else None,
        }
