"""Scheduler tasks — computational priority only, never trading authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ResourceClass(str, Enum):
    SAFETY = "SAFETY"
    RESEARCH = "RESEARCH"
    MAINTENANCE = "MAINTENANCE"


class MarketPhase(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PREOPEN = "PREOPEN"


class SchedulerDecision(str, Enum):
    RUN = "RUN"
    QUEUE = "QUEUE"
    DEFER = "DEFER"
    BLOCK = "BLOCK"
    DROP = "DROP"


RESOURCE_PRIORITY = {
    ResourceClass.SAFETY: 30,
    ResourceClass.RESEARCH: 20,
    ResourceClass.MAINTENANCE: 10,
}


@dataclass
class OrchTask:
    task_id: str
    resource_class: ResourceClass
    priority: int = 0
    urgency: int = 0
    evidence_available: bool = True
    dependencies: list[str] = field(default_factory=list)
    market_phase: MarketPhase = MarketPhase.OPEN
    estimated_cost: float = 0.0
    attempt: int = 0
    retry_policy: dict[str, Any] = field(default_factory=lambda: {"max_attempts": 3})


def create_task(
    task_id: str,
    resource_class: ResourceClass,
    *,
    priority: int = 0,
    urgency: int = 0,
    evidence_available: bool = True,
    dependencies: Optional[list[str]] = None,
    market_phase: MarketPhase = MarketPhase.OPEN,
    estimated_cost: float = 0.0,
) -> OrchTask:
    return OrchTask(
        task_id=task_id,
        resource_class=resource_class,
        priority=priority,
        urgency=urgency,
        evidence_available=evidence_available,
        dependencies=list(dependencies or []),
        market_phase=market_phase,
        estimated_cost=estimated_cost,
    )
